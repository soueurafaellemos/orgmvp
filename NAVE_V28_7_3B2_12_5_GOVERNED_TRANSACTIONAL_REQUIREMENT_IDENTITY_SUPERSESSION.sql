-- NAVE by VOE
-- V28.7.3B2.12.5 — Governed Transactional Requirement Identity Supersession
--
-- FIRST REAL WRITE in the B2.12.x identity-collision sequence.
--
-- Contract:
-- - one PostgreSQL transaction per RPC call;
-- - project-scoped advisory transaction lock;
-- - fresh B2.12.4.1 dry-run bundle required;
-- - H3.1.3P1 promotion token required;
-- - fail closed on every identity / lifecycle / occurrence / alias mismatch;
-- - never DELETE;
-- - never copy conflicting business metadata from superseded identity to survivor;
-- - never mutate historical semantic observations;
-- - preserve all historical Domain Evidence links;
-- - occurrence duplicates become superseded, rebinds use the dry-run target hash;
-- - only a coalesced SOURCE evidence link may be inserted;
-- - postconditions execute before COMMIT; any failure raises and rolls back everything;
-- - requirements remain shadow_compare; no domain_primary/canary change;
-- - no response adjudication Truth effect and no Human Review synthesis.

begin;

create or replace function public.apply_project_requirement_identity_supersession_b2125(
  p_project_id uuid,
  p_run_id uuid,
  p_confirmation_token text,
  p_pipeline_promotion_version text,
  p_execution_bundle jsonb,
  p_execution_signature text
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  c_version constant text := 'V28.7.3B2.12.5';
  c_dry_run_version constant text := 'V28.7.3B2.12.4.1';
  c_promotion_version constant text := 'V28.7.2C0.2.4H3.1.3P1';

  v_dry jsonb;
  v_plan jsonb;
  v_exec_plan jsonb;
  v_project_entity_id uuid;
  v_read_mode text;

  v_survivor_id uuid;
  v_survivor_entity_id uuid;
  v_superseded_ids uuid[];
  v_superseded_entity_ids uuid[];
  v_aliases uuid[];

  v_expected_current_before integer;
  v_expected_current_after integer;
  v_current_before integer;
  v_current_after integer;

  v_survivor_pr public.project_requirements%rowtype;
  v_survivor_gov public.domain_object_governance%rowtype;
  v_survivor_ke public.knowledge_entities%rowtype;
  v_old_pr public.project_requirements%rowtype;
  v_old_gov public.domain_object_governance%rowtype;
  v_old_ke public.knowledge_entities%rowtype;
  v_occ public.project_requirement_occurrences%rowtype;
  v_target_occ public.project_requirement_occurrences%rowtype;

  v_survivor_business_before jsonb;
  v_survivor_business_after jsonb;
  v_survivor_review_before text;

  v_old_id uuid;
  v_old_entity_id uuid;
  v_alias uuid;
  v_action jsonb;
  v_evidence_action jsonb;
  v_action_count integer;
  v_target_occurrence_id uuid;
  v_target_hash text;
  v_alias_target_count integer;
  v_alias_target_id uuid;

  v_old_evidence_before integer := 0;
  v_old_evidence_after integer := 0;
  v_semantic_before integer := 0;
  v_semantic_after integer := 0;
  v_inserted_source_links integer := 0;
  v_occurrences_superseded integer := 0;
  v_occurrences_rebound integer := 0;

  v_context jsonb;
  v_context_sha text;
  v_binding_confidence numeric;
  v_metadata_conflicts jsonb;
  v_result jsonb;
begin
  if p_project_id is null or p_run_id is null then
    raise exception 'B2.12.5 requires project_id and run_id';
  end if;

  if coalesce(p_confirmation_token,'') <> 'SUPERSEDE:' || p_project_id::text then
    raise exception 'B2.12.5 explicit confirmation token mismatch';
  end if;

  if coalesce(p_pipeline_promotion_version,'') <> c_promotion_version then
    raise exception 'B2.12.5 H3.1.3P1 promotion precondition failed: %', p_pipeline_promotion_version;
  end if;

  if p_execution_bundle is null then
    raise exception 'B2.12.5 execution bundle missing';
  end if;

  -- Serialize all Requirement identity supersessions for this project.
  perform pg_advisory_xact_lock(
    hashtextextended('nave:b2125:' || p_project_id::text, 0)
  );

  select read_mode
  into v_read_mode
  from public.project_domain_cutover_readiness
  where project_id = p_project_id
    and domain_key = 'requirements'
  limit 1;

  if coalesce(v_read_mode,'') <> 'shadow_compare' then
    raise exception 'B2.12.5 requires requirements read_mode=shadow_compare, got %', v_read_mode;
  end if;

  select id
  into v_project_entity_id
  from public.knowledge_entities
  where domain_table = 'projects'
    and domain_id = p_project_id
  order by created_at asc
  limit 1;

  if v_project_entity_id is null then
    raise exception 'B2.12.5 project knowledge_entity missing';
  end if;

  if coalesce(p_execution_bundle->>'bundle_version','') <> c_version then
    raise exception 'B2.12.5 execution bundle version mismatch';
  end if;

  if coalesce(p_execution_bundle->>'pipeline_promotion_version','') <> c_promotion_version then
    raise exception 'B2.12.5 bundle promotion version mismatch';
  end if;

  v_dry := p_execution_bundle->'dry_run_report';
  v_exec_plan := p_execution_bundle->'execution_plan';

  if coalesce(v_dry->>'version','') <> c_dry_run_version then
    raise exception 'B2.12.5 requires fresh B2.12.4.1 dry-run';
  end if;

  if coalesce(v_dry->>'project_id','') <> p_project_id::text then
    raise exception 'B2.12.5 dry-run project mismatch';
  end if;

  if coalesce((v_dry->>'transaction_plan_count')::integer,0) <> 1
     or coalesce((v_dry->>'ready_transaction_plan_count')::integer,0) <> 1
     or coalesce((v_dry->>'blocked_transaction_plan_count')::integer,0) <> 0
     or jsonb_array_length(coalesce(v_dry->'plans','[]'::jsonb)) <> 1 then
    raise exception 'B2.12.5 requires exactly one ready, unblocked transaction plan';
  end if;

  v_plan := v_dry->'plans'->0;

  if jsonb_array_length(coalesce(v_plan->'blockers','[]'::jsonb)) <> 0 then
    raise exception 'B2.12.5 dry-run plan contains blockers';
  end if;

  if coalesce(v_plan->>'compatibility_status_after','') <> 'PASS_DATA_BRIDGE' then
    raise exception 'B2.12.5 dry-run B2.1 compatibility is not PASS';
  end if;

  if coalesce((v_plan->>'projected_collisions_after')::integer,-1) <> 0 then
    raise exception 'B2.12.5 dry-run does not project collision count 0';
  end if;

  v_survivor_id := nullif(v_plan->>'survivor_requirement_id','')::uuid;
  v_survivor_entity_id := nullif(v_plan->>'survivor_entity_id','')::uuid;
  v_expected_current_before := (v_plan->>'current_before')::integer;
  v_expected_current_after := (v_plan->>'projected_current_after')::integer;
  v_metadata_conflicts := coalesce(v_plan->'metadata_conflicts','[]'::jsonb);

  select array_agg(value::uuid order by value)
  into v_superseded_ids
  from jsonb_array_elements_text(
    coalesce(v_plan->'superseded_requirement_ids','[]'::jsonb)
  );

  select array_agg(value::uuid order by value)
  into v_superseded_entity_ids
  from jsonb_array_elements_text(
    coalesce(v_plan->'superseded_entity_ids','[]'::jsonb)
  );

  if v_survivor_id is null or v_survivor_entity_id is null then
    raise exception 'B2.12.5 survivor identity/entity missing';
  end if;

  if coalesce(array_length(v_superseded_ids,1),0) = 0
     or coalesce(array_length(v_superseded_ids,1),0)
        <> coalesce(array_length(v_superseded_entity_ids,1),0) then
    raise exception 'B2.12.5 superseded identity/entity cardinality mismatch';
  end if;

  -- Execution plan must be a faithful executable projection of the dry-run identity plan.
  if coalesce(v_exec_plan->>'survivor_requirement_id','') <> v_survivor_id::text
     or coalesce(v_exec_plan->>'survivor_entity_id','') <> v_survivor_entity_id::text
     or coalesce(v_exec_plan->'superseded_requirement_ids','[]'::jsonb)
        <> coalesce(v_plan->'superseded_requirement_ids','[]'::jsonb)
     or coalesce(v_exec_plan->'superseded_entity_ids','[]'::jsonb)
        <> coalesce(v_plan->'superseded_entity_ids','[]'::jsonb) then
    raise exception 'B2.12.5 execution plan identity projection mismatch';
  end if;

  select count(*)::integer
  into v_current_before
  from public.project_requirement_truth_status
  where project_id = p_project_id
    and truth_state in ('verified','human_confirmed');

  if v_current_before <> v_expected_current_before then
    raise exception 'B2.12.5 stale precondition: Current count expected %, got %',
      v_expected_current_before, v_current_before;
  end if;

  select *
  into v_survivor_pr
  from public.project_requirements
  where id = v_survivor_id
    and project_id = p_project_id
  for update;

  if not found then
    raise exception 'B2.12.5 survivor project_requirement missing';
  end if;

  if v_survivor_pr.entity_id is distinct from v_survivor_entity_id
     or coalesce(v_survivor_pr.status,'active') <> 'active' then
    raise exception 'B2.12.5 survivor identity/entity/status precondition failed';
  end if;

  if not exists (
    select 1
    from public.project_requirement_truth_status
    where project_id = p_project_id
      and id = v_survivor_id
      and truth_state in ('verified','human_confirmed')
  ) then
    raise exception 'B2.12.5 survivor is not Current Requirement Truth';
  end if;

  select *
  into v_survivor_gov
  from public.domain_object_governance
  where entity_id = v_survivor_entity_id
  for update;

  if not found or coalesce(v_survivor_gov.lifecycle_status,'active') <> 'active' then
    raise exception 'B2.12.5 survivor governance missing/not active';
  end if;

  v_survivor_review_before := v_survivor_gov.review_status;

  select *
  into v_survivor_ke
  from public.knowledge_entities
  where id = v_survivor_entity_id
  for update;

  if not found
     or coalesce(v_survivor_ke.domain_table,'') <> 'project_requirements'
     or v_survivor_ke.domain_id <> v_survivor_id
     or coalesce(v_survivor_ke.status,'active') <> 'active'
     or (
       v_survivor_ke.canonical_entity_id is not null
       and v_survivor_ke.canonical_entity_id <> v_survivor_entity_id
     ) then
    raise exception 'B2.12.5 survivor knowledge_entity precondition failed';
  end if;

  v_survivor_business_before := jsonb_build_object(
    'requirement_type', v_survivor_pr.requirement_type,
    'title', v_survivor_pr.title,
    'description', v_survivor_pr.description,
    'priority', v_survivor_pr.priority,
    'mandatory', v_survivor_pr.mandatory,
    'constraint_operator', v_survivor_pr.constraint_operator,
    'constraint_value', v_survivor_pr.constraint_value,
    'unit', v_survivor_pr.unit,
    'status', v_survivor_pr.status,
    'confidence', v_survivor_pr.confidence,
    'attributes', coalesce(v_survivor_pr.attributes,'{}'::jsonb)
  );

  -- Lock and validate every superseded identity.
  for v_action_count in 1..array_length(v_superseded_ids,1)
  loop
    v_old_id := v_superseded_ids[v_action_count];
    v_old_entity_id := v_superseded_entity_ids[v_action_count];

    if v_old_id = v_survivor_id or v_old_entity_id = v_survivor_entity_id then
      raise exception 'B2.12.5 survivor cannot supersede itself';
    end if;

    select *
    into v_old_pr
    from public.project_requirements
    where id = v_old_id
      and project_id = p_project_id
    for update;

    if not found
       or v_old_pr.entity_id is distinct from v_old_entity_id
       or coalesce(v_old_pr.status,'active') <> 'active' then
      raise exception 'B2.12.5 superseded Requirement precondition failed: %', v_old_id;
    end if;

    if not exists (
      select 1
      from public.project_requirement_truth_status
      where project_id = p_project_id
        and id = v_old_id
        and truth_state in ('verified','human_confirmed')
    ) then
      raise exception 'B2.12.5 superseded Requirement is not Current: %', v_old_id;
    end if;

    select *
    into v_old_gov
    from public.domain_object_governance
    where entity_id = v_old_entity_id
    for update;

    if not found
       or coalesce(v_old_gov.lifecycle_status,'active') <> 'active'
       or v_old_gov.superseded_by_entity_id is not null then
      raise exception 'B2.12.5 superseded governance precondition failed: %', v_old_id;
    end if;

    select *
    into v_old_ke
    from public.knowledge_entities
    where id = v_old_entity_id
    for update;

    if not found
       or coalesce(v_old_ke.domain_table,'') <> 'project_requirements'
       or v_old_ke.domain_id <> v_old_id
       or coalesce(v_old_ke.status,'active') <> 'active'
       or (
         v_old_ke.canonical_entity_id is not null
         and v_old_ke.canonical_entity_id <> v_old_entity_id
       ) then
      raise exception 'B2.12.5 superseded knowledge_entity precondition failed: %', v_old_id;
    end if;
  end loop;

  -- Capture aliases BEFORE occurrence mutation.
  select array_agg(distinct alias order by alias)
  into v_aliases
  from (
    select pr.legacy_source_id as alias
    from public.project_requirements pr
    where pr.id = any(v_superseded_ids)
      and pr.legacy_source_id is not null
    union
    select pro.legacy_requirement_id as alias
    from public.project_requirement_occurrences pro
    where pro.project_id = p_project_id
      and pro.requirement_id = any(v_superseded_ids)
      and pro.legacy_requirement_id is not null
  ) q;

  select count(*)::integer
  into v_old_evidence_before
  from public.domain_object_evidence
  where project_id = p_project_id
    and domain_table = 'project_requirements'
    and object_entity_id = any(v_superseded_entity_ids);

  select count(*)::integer
  into v_semantic_before
  from public.semantic_observations
  where project_id = p_project_id
    and domain_hint = 'requirement'
    and resolved_domain_id = any(v_superseded_ids);

  -- Transaction audit row is part of THIS transaction: failure later rolls it back too.
  insert into public.intelligence_runs(
    id, analyzer_type, scope_kind, scope_entity_id,
    pipeline_version, code_version, schema_version,
    input_signature, status, started_at, metadata
  ) values (
    p_run_id,
    'project_requirement_identity_supersession',
    'project',
    v_project_entity_id,
    c_version,
    c_version,
    '28.7.3b2.12.5',
    p_execution_signature,
    'running',
    now(),
    jsonb_build_object(
      'project_id', p_project_id,
      'survivor_requirement_id', v_survivor_id,
      'survivor_entity_id', v_survivor_entity_id,
      'superseded_requirement_ids', to_jsonb(v_superseded_ids),
      'superseded_entity_ids', to_jsonb(v_superseded_entity_ids),
      'legacy_aliases', coalesce(to_jsonb(v_aliases),'[]'::jsonb),
      'metadata_conflicts', v_metadata_conflicts,
      'current_before', v_current_before,
      'expected_current_after', v_expected_current_after,
      'old_evidence_count_before', v_old_evidence_before,
      'semantic_observation_count_before', v_semantic_before,
      'survivor_business_metadata_before', v_survivor_business_before,
      'survivor_review_status_before', v_survivor_review_before,
      'dry_run_version', c_dry_run_version,
      'pipeline_promotion_version', c_promotion_version,
      'transaction_fail_closed', true,
      'response_truth_changed', false,
      'human_review_created', false,
      'cutover_changed', false
    )
  );

  -- Occurrence actions are executed exactly as the fresh dry-run projected.
  for v_old_id in
    select unnest(v_superseded_ids)
  loop
    for v_occ in
      select *
      from public.project_requirement_occurrences
      where project_id = p_project_id
        and requirement_id = v_old_id
        and lifecycle_status = 'active'
      for update
    loop
      select count(*)::integer
      into v_action_count
      from jsonb_array_elements(
        coalesce(v_exec_plan->'occurrence_actions','[]'::jsonb)
      )
      where value->>'occurrence_id' = v_occ.id::text;

      if v_action_count <> 1 then
        raise exception 'B2.12.5 missing/ambiguous occurrence action for %', v_occ.id;
      end if;

      select value
      into v_action
      from jsonb_array_elements(
        coalesce(v_exec_plan->'occurrence_actions','[]'::jsonb)
      )
      where value->>'occurrence_id' = v_occ.id::text
      limit 1;

      if coalesce(v_action->>'from_requirement_id','') <> v_old_id::text
         or coalesce(v_action->>'to_requirement_id','') <> v_survivor_id::text then
        raise exception 'B2.12.5 occurrence action identity mismatch for %', v_occ.id;
      end if;

      v_target_hash := nullif(v_action->>'target_occurrence_hash','');

      if v_action->>'action' = 'supersede_duplicate_occurrence' then
        v_target_occurrence_id := nullif(
          v_action->>'existing_survivor_occurrence_id',''
        )::uuid;

        select *
        into v_target_occ
        from public.project_requirement_occurrences
        where id = v_target_occurrence_id
        for update;

        if not found
           or v_target_occ.project_id is distinct from p_project_id
           or v_target_occ.requirement_id is distinct from v_survivor_id
           or v_target_occ.lifecycle_status <> 'active'
           or v_target_occ.evidence_unit_id is distinct from v_occ.evidence_unit_id
           or coalesce(v_target_occ.occurrence_role,'requirement')
              <> coalesce(v_occ.occurrence_role,'requirement')
           or coalesce(v_target_occ.occurrence_hash,'') <> coalesce(v_target_hash,'') then
          raise exception 'B2.12.5 duplicate occurrence target precondition failed for %', v_occ.id;
        end if;

        update public.project_requirement_occurrences
        set lifecycle_status = 'superseded',
            attributes = coalesce(attributes,'{}'::jsonb)
              || jsonb_build_object(
                'identity_resolution',
                jsonb_build_object(
                  'version', c_version,
                  'run_id', p_run_id,
                  'from_requirement_id', v_old_id,
                  'canonical_requirement_id', v_survivor_id,
                  'survivor_occurrence_id', v_target_occurrence_id,
                  'action', 'supersede_duplicate_occurrence'
                )
              ),
            updated_at = now()
        where id = v_occ.id;

        v_occurrences_superseded := v_occurrences_superseded + 1;

      elsif v_action->>'action' = 'rebind_occurrence' then
        if v_target_hash is null then
          raise exception 'B2.12.5 rebind target hash missing for %', v_occ.id;
        end if;

        if exists (
          select 1
          from public.project_requirement_occurrences
          where occurrence_hash = v_target_hash
            and id <> v_occ.id
        ) then
          raise exception 'B2.12.5 rebind target occurrence hash already exists for %', v_occ.id;
        end if;

        update public.project_requirement_occurrences
        set requirement_id = v_survivor_id,
            occurrence_hash = v_target_hash,
            attributes = coalesce(attributes,'{}'::jsonb)
              || jsonb_build_object(
                'identity_resolution',
                jsonb_build_object(
                  'version', c_version,
                  'run_id', p_run_id,
                  'from_requirement_id', v_old_id,
                  'canonical_requirement_id', v_survivor_id,
                  'action', 'rebind_occurrence'
                )
              ),
            updated_at = now()
        where id = v_occ.id;

        v_occurrences_rebound := v_occurrences_rebound + 1;
      else
        raise exception 'B2.12.5 unsupported occurrence action: %', v_action->>'action';
      end if;
    end loop;
  end loop;

  -- Alias actions. This is a compatibility bridge, not business metadata merge.
  for v_action in
    select value
    from jsonb_array_elements(
      coalesce(v_exec_plan->'alias_actions','[]'::jsonb)
    )
  loop
    v_alias := nullif(v_action->>'alias','')::uuid;

    if v_alias is null
       or not (v_alias = any(coalesce(v_aliases, array[]::uuid[]))) then
      raise exception 'B2.12.5 alias action is not sourced from superseded identity';
    end if;

    if v_action->>'action' = 'set_survivor_legacy_source_id' then
      if v_survivor_pr.legacy_source_id is not null
         and v_survivor_pr.legacy_source_id <> v_alias then
        raise exception 'B2.12.5 survivor already carries a different legacy_source_id';
      end if;

      update public.project_requirements
      set legacy_source_table = coalesce(legacy_source_table, 'memory_briefing_requirements'),
          legacy_source_id = v_alias,
          updated_at = now()
      where id = v_survivor_id
        and project_id = p_project_id;

    elsif v_action->>'action' = 'already_on_survivor_legacy_source_id' then
      if v_survivor_pr.legacy_source_id <> v_alias then
        raise exception 'B2.12.5 expected alias is not already on survivor';
      end if;
    else
      raise exception 'B2.12.5 unsupported alias action: %', v_action->>'action';
    end if;
  end loop;

  -- Evidence actions: historical links are NEVER deleted/rewritten.
  -- Occurrence evidence is reused. At most one coalesced SOURCE link is inserted.
  for v_evidence_action in
    select value
    from jsonb_array_elements(
      coalesce(v_exec_plan->'evidence_actions','[]'::jsonb)
    )
  loop
    if v_evidence_action->>'action' = 'reuse_existing_survivor_evidence_link' then
      if not exists (
        select 1
        from public.domain_object_evidence
        where project_id = p_project_id
          and object_entity_id = v_survivor_entity_id
          and domain_table = 'project_requirements'
          and domain_id = v_survivor_id
          and evidence_unit_id = (v_evidence_action->>'evidence_unit_id')::uuid
          and link_role = v_evidence_action->>'link_role'
      ) then
        raise exception 'B2.12.5 expected survivor evidence link is missing';
      end if;

    elsif v_evidence_action->>'action' = 'insert_single_survivor_evidence_link' then
      if v_evidence_action->>'link_role' <> 'source' then
        raise exception 'B2.12.5 only a coalesced SOURCE evidence insert is allowed';
      end if;

      v_context := coalesce(v_evidence_action->'context','{}'::jsonb);
      v_context_sha := nullif(v_evidence_action->>'context_sha256','');

      if coalesce(v_context->'identity_resolution'->>'version','') <> c_version
         or coalesce(v_context->'identity_resolution'->>'canonical_requirement_id','')
            <> v_survivor_id::text
         or v_context_sha is null then
        raise exception 'B2.12.5 source evidence execution context invalid';
      end if;

      select max(binding_confidence)
      into v_binding_confidence
      from public.domain_object_evidence
      where project_id = p_project_id
        and object_entity_id = any(v_superseded_entity_ids)
        and evidence_unit_id = (v_evidence_action->>'evidence_unit_id')::uuid
        and link_role = 'source';

      insert into public.domain_object_evidence(
        project_id, object_entity_id, domain_table, domain_id,
        evidence_unit_id, link_role, context, context_sha256,
        binding_confidence, normalization_run_id
      ) values (
        p_project_id,
        v_survivor_entity_id,
        'project_requirements',
        v_survivor_id,
        (v_evidence_action->>'evidence_unit_id')::uuid,
        'source',
        v_context,
        v_context_sha,
        v_binding_confidence,
        p_run_id
      )
      on conflict (object_entity_id,evidence_unit_id,link_role,context_sha256)
      do nothing;

      get diagnostics v_action_count = row_count;
      v_inserted_source_links := v_inserted_source_links + v_action_count;
    else
      raise exception 'B2.12.5 unsupported evidence action: %',
        v_evidence_action->>'action';
    end if;
  end loop;

  -- Supersede identities only AFTER occurrence/alias/evidence preconditions passed.
  for v_action_count in 1..array_length(v_superseded_ids,1)
  loop
    v_old_id := v_superseded_ids[v_action_count];
    v_old_entity_id := v_superseded_entity_ids[v_action_count];

    update public.project_requirements
    set status = 'superseded',
        updated_at = now()
    where id = v_old_id
      and project_id = p_project_id;

    update public.domain_object_governance
    set lifecycle_status = 'superseded',
        superseded_by_entity_id = v_survivor_entity_id,
        last_normalization_run_id = p_run_id,
        metadata = coalesce(metadata,'{}'::jsonb)
          || jsonb_build_object(
            'identity_resolution',
            jsonb_build_object(
              'version', c_version,
              'run_id', p_run_id,
              'canonical_requirement_id', v_survivor_id
            )
          ),
        updated_at = now()
    where entity_id = v_old_entity_id;

    update public.knowledge_entities
    set status = 'merged',
        canonical_entity_id = v_survivor_entity_id,
        attributes = coalesce(attributes,'{}'::jsonb)
          || jsonb_build_object(
            'identity_resolution',
            jsonb_build_object(
              'version', c_version,
              'run_id', p_run_id,
              'canonical_requirement_id', v_survivor_id
            )
          ),
        updated_at = now()
    where id = v_old_entity_id;
  end loop;

  -- ---------------------------
  -- FAIL-CLOSED POSTCONDITIONS
  -- ---------------------------

  select count(*)::integer
  into v_current_after
  from public.project_requirement_truth_status
  where project_id = p_project_id
    and truth_state in ('verified','human_confirmed');

  if v_current_after <> v_expected_current_after then
    raise exception 'B2.12.5 postcondition Current count expected %, got %',
      v_expected_current_after, v_current_after;
  end if;

  if not exists (
    select 1
    from public.project_requirement_truth_status
    where project_id = p_project_id
      and id = v_survivor_id
      and truth_state in ('verified','human_confirmed')
  ) then
    raise exception 'B2.12.5 postcondition survivor is not Current';
  end if;

  for v_action_count in 1..array_length(v_superseded_ids,1)
  loop
    v_old_id := v_superseded_ids[v_action_count];
    v_old_entity_id := v_superseded_entity_ids[v_action_count];

    if not exists (
      select 1
      from public.project_requirement_truth_status
      where project_id = p_project_id
        and id = v_old_id
        and truth_state = 'historical'
    ) then
      raise exception 'B2.12.5 postcondition superseded identity is not historical: %', v_old_id;
    end if;

    if exists (
      select 1
      from public.project_requirement_occurrences
      where project_id = p_project_id
        and requirement_id = v_old_id
        and lifecycle_status = 'active'
    ) then
      raise exception 'B2.12.5 postcondition active occurrence remains on old identity: %', v_old_id;
    end if;

    if not exists (
      select 1
      from public.domain_object_governance
      where entity_id = v_old_entity_id
        and lifecycle_status = 'superseded'
        and superseded_by_entity_id = v_survivor_entity_id
    ) then
      raise exception 'B2.12.5 postcondition governance lineage failed: %', v_old_id;
    end if;

    if not exists (
      select 1
      from public.knowledge_entities
      where id = v_old_entity_id
        and status = 'merged'
        and canonical_entity_id = v_survivor_entity_id
    ) then
      raise exception 'B2.12.5 postcondition knowledge entity lineage failed: %', v_old_id;
    end if;
  end loop;

  -- Each historical Legacy alias must resolve structurally to ONE Current identity: survivor.
  if v_aliases is not null then
    foreach v_alias in array v_aliases
    loop
      select count(distinct requirement_id)
      into v_alias_target_count
      from (
        select t.id as requirement_id
        from public.project_requirement_truth_status t
        where t.project_id = p_project_id
          and t.truth_state in ('verified','human_confirmed')
          and t.legacy_source_id = v_alias
        union
        select pro.requirement_id
        from public.project_requirement_occurrences pro
        join public.project_requirement_truth_status t
          on t.id = pro.requirement_id
         and t.project_id = p_project_id
         and t.truth_state in ('verified','human_confirmed')
        where pro.project_id = p_project_id
          and pro.lifecycle_status = 'active'
          and pro.legacy_requirement_id = v_alias
      ) mapped;

      select requirement_id
      into v_alias_target_id
      from (
        select t.id as requirement_id
        from public.project_requirement_truth_status t
        where t.project_id = p_project_id
          and t.truth_state in ('verified','human_confirmed')
          and t.legacy_source_id = v_alias
        union
        select pro.requirement_id
        from public.project_requirement_occurrences pro
        join public.project_requirement_truth_status t
          on t.id = pro.requirement_id
         and t.project_id = p_project_id
         and t.truth_state in ('verified','human_confirmed')
        where pro.project_id = p_project_id
          and pro.lifecycle_status = 'active'
          and pro.legacy_requirement_id = v_alias
      ) mapped
      limit 1;

      if v_alias_target_count <> 1 or v_alias_target_id is distinct from v_survivor_id then
        raise exception 'B2.12.5 postcondition Legacy alias not uniquely mapped to survivor: %', v_alias;
      end if;
    end loop;
  end if;

  select count(*)::integer
  into v_old_evidence_after
  from public.domain_object_evidence
  where project_id = p_project_id
    and domain_table = 'project_requirements'
    and object_entity_id = any(v_superseded_entity_ids);

  if v_old_evidence_after <> v_old_evidence_before then
    raise exception 'B2.12.5 historical evidence links changed: % -> %',
      v_old_evidence_before, v_old_evidence_after;
  end if;

  select count(*)::integer
  into v_semantic_after
  from public.semantic_observations
  where project_id = p_project_id
    and domain_hint = 'requirement'
    and resolved_domain_id = any(v_superseded_ids);

  if v_semantic_after <> v_semantic_before then
    raise exception 'B2.12.5 historical semantic observations changed: % -> %',
      v_semantic_before, v_semantic_after;
  end if;

  select jsonb_build_object(
    'requirement_type', pr.requirement_type,
    'title', pr.title,
    'description', pr.description,
    'priority', pr.priority,
    'mandatory', pr.mandatory,
    'constraint_operator', pr.constraint_operator,
    'constraint_value', pr.constraint_value,
    'unit', pr.unit,
    'status', pr.status,
    'confidence', pr.confidence,
    'attributes', coalesce(pr.attributes,'{}'::jsonb)
  )
  into v_survivor_business_after
  from public.project_requirements pr
  where pr.id = v_survivor_id
    and pr.project_id = p_project_id;

  if v_survivor_business_after <> v_survivor_business_before then
    raise exception 'B2.12.5 survivor business metadata changed unexpectedly';
  end if;

  if (
    select review_status
    from public.domain_object_governance
    where entity_id = v_survivor_entity_id
  ) is distinct from v_survivor_review_before then
    raise exception 'B2.12.5 survivor Human Review status changed unexpectedly';
  end if;

  select read_mode
  into v_read_mode
  from public.project_domain_cutover_readiness
  where project_id = p_project_id
    and domain_key = 'requirements'
  limit 1;

  if coalesce(v_read_mode,'') <> 'shadow_compare' then
    raise exception 'B2.12.5 postcondition read_mode changed unexpectedly';
  end if;

  v_result := jsonb_build_object(
    'version', c_version,
    'status', 'COMPLETED_TRANSACTIONAL_SUPERSESSION',
    'run_id', p_run_id,
    'project_id', p_project_id,
    'survivor_requirement_id', v_survivor_id,
    'survivor_entity_id', v_survivor_entity_id,
    'superseded_requirement_ids', to_jsonb(v_superseded_ids),
    'superseded_entity_ids', to_jsonb(v_superseded_entity_ids),
    'legacy_aliases', coalesce(to_jsonb(v_aliases),'[]'::jsonb),
    'current_before', v_current_before,
    'current_after', v_current_after,
    'occurrences_superseded', v_occurrences_superseded,
    'occurrences_rebound', v_occurrences_rebound,
    'source_evidence_links_inserted', v_inserted_source_links,
    'historical_evidence_links_preserved', v_old_evidence_after,
    'semantic_observations_preserved', v_semantic_after,
    'survivor_business_metadata_preserved', true,
    'requirement_truth_changed', true,
    'response_truth_changed', false,
    'human_review_created', false,
    'cutover_changed', false,
    'read_mode', v_read_mode
  );

  update public.intelligence_runs
  set status = 'completed',
      completed_at = now(),
      output_signature = pg_catalog.encode(
        pg_catalog.sha256(
          pg_catalog.convert_to(v_result::text,'UTF8')
        ),
        'hex'
      ),
      metadata = coalesce(metadata,'{}'::jsonb)
        || jsonb_build_object(
          'current_after', v_current_after,
          'occurrences_superseded', v_occurrences_superseded,
          'occurrences_rebound', v_occurrences_rebound,
          'source_evidence_links_inserted', v_inserted_source_links,
          'old_evidence_count_after', v_old_evidence_after,
          'semantic_observation_count_after', v_semantic_after,
          'survivor_business_metadata_after', v_survivor_business_after,
          'survivor_business_metadata_preserved', true,
          'requirement_truth_changed', true,
          'response_truth_changed', false,
          'human_review_created', false,
          'cutover_changed', false
        )
  where id = p_run_id;

  return v_result;

exception when others then
  -- PostgreSQL rolls back every mutation in this function call.
  raise;
end;
$$;

comment on function public.apply_project_requirement_identity_supersession_b2125(
  uuid,uuid,text,text,jsonb,text
) is
  'V28.7.3B2.12.5 — fail-closed transactional Requirement identity supersession. Preserves historical evidence/semantic observations and survivor business metadata; no response Truth effect.';

revoke all on function public.apply_project_requirement_identity_supersession_b2125(
  uuid,uuid,text,text,jsonb,text
) from anon, authenticated;

grant execute on function public.apply_project_requirement_identity_supersession_b2125(
  uuid,uuid,text,text,jsonb,text
) to service_role;

commit;
