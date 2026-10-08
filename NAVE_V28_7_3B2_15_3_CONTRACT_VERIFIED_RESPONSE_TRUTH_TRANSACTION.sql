-- NAVE by VOE
-- V28.7.3B2.15.3 — CONTRACT-VERIFIED RESPONSE TRUTH TRANSACTION + ROLLBACK PROBE
--
-- INSTALLATION ONLY. NO RESPONSE TRUTH IS WRITTEN BY INSTALLING THIS SQL.
--
-- Installs:
--   1) fail-closed transactional bootstrap writer RPC;
--   2) rollback-only diagnostic wrapper.
--
-- Scope intentionally excludes machine recommendations, Human Review,
-- human_confirmed_response, revocation, identity transfer and cutover changes.

begin;

create or replace function public.apply_contract_verified_response_truth_b2153(
    p_project_id uuid,
    p_run_id uuid,
    p_confirmation_token text,
    p_review_fingerprint text,
    p_projection_version text,
    p_execution_bundle jsonb,
    p_execution_signature text
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    c_version constant text := 'V28.7.3B2.15.3';
    c_projection_version constant text := 'V28.7.3B2.15.2.1';
    c_contract_version constant text := 'V28.7.3B2.7.1';

    v_read_mode text;
    v_project_entity_id uuid;
    v_events jsonb;
    v_event jsonb;
    v_evidence jsonb;

    v_event_count integer := 0;
    v_expected_evidence_count integer := 0;
    v_inserted_event_count integer := 0;
    v_inserted_evidence_count integer := 0;

    v_event_id uuid;
    v_requirement_id uuid;
    v_requirement_entity_id uuid;
    v_event_signature text;
    v_evidence_unit_id uuid;

    v_event_signature_list text;
    v_expected_execution_signature text;

    v_requirement_current_before integer := 0;
    v_requirement_current_after integer := 0;
    v_review_before integer := 0;
    v_review_after integer := 0;
    v_domain_evidence_before integer := 0;
    v_domain_evidence_after integer := 0;

    v_target_current_truth_count integer := 0;
    v_target_status_count integer := 0;

    v_event_ids jsonb := '[]'::jsonb;
    v_event_signatures jsonb := '[]'::jsonb;
    v_result jsonb;
begin
    if p_project_id is null or p_run_id is null then
        raise exception 'B2.15.3 requires project_id and run_id';
    end if;

    perform pg_advisory_xact_lock(
        hashtextextended('nave:b2153:' || p_project_id::text, 0)
    );

    select read_mode
      into v_read_mode
      from public.project_domain_cutover_readiness
     where project_id = p_project_id
       and domain_key = 'requirements';

    if v_read_mode is distinct from 'shadow_compare' then
        raise exception
            'B2.15.3 requires requirements read_mode=shadow_compare; got %',
            coalesce(v_read_mode,'<missing>');
    end if;

    if p_projection_version is distinct from c_projection_version then
        raise exception
            'B2.15.3 projection version mismatch: expected %, got %',
            c_projection_version,
            coalesce(p_projection_version,'<null>');
    end if;

    if coalesce(p_execution_bundle->>'version','') <> c_version
       or coalesce(p_execution_bundle->>'project_id','') <> p_project_id::text
       or coalesce(p_execution_bundle->>'projection_version','') <> c_projection_version
       or coalesce(p_execution_bundle->>'contract_version','') <> c_contract_version then
        raise exception 'B2.15.3 execution bundle contract mismatch';
    end if;

    v_events := coalesce(p_execution_bundle->'events','[]'::jsonb);
    if jsonb_typeof(v_events) <> 'array' then
        raise exception 'B2.15.3 execution bundle events must be an array';
    end if;

    v_event_count := jsonb_array_length(v_events);
    if v_event_count < 1 then
        raise exception 'B2.15.3 refuses empty real-write transactions';
    end if;

    select string_agg(value->>'event_signature', ',' order by value->>'event_signature')
      into v_event_signature_list
      from jsonb_array_elements(v_events);

    if v_event_signature_list is null or v_event_signature_list = '' then
        raise exception 'B2.15.3 event signatures missing';
    end if;

    v_expected_execution_signature := pg_catalog.encode(
        pg_catalog.sha256(
            pg_catalog.convert_to(
                c_version || '|' || p_project_id::text || '|' || v_event_signature_list,
                'UTF8'
            )
        ),
        'hex'
    );

    if p_execution_signature is distinct from v_expected_execution_signature
       or p_review_fingerprint is distinct from v_expected_execution_signature then
        raise exception 'B2.15.3 reviewed transaction fingerprint/signature mismatch';
    end if;

    if p_confirmation_token is distinct from
        (
            'WRITE_RESPONSE_TRUTH:'
            || p_project_id::text
            || ':'
            || left(v_expected_execution_signature,12)
        ) then
        raise exception 'B2.15.3 explicit confirmation token mismatch';
    end if;

    -- Bootstrap-only fail closed: the new ledger must still be empty.
    if exists (
        select 1 from public.project_requirement_response_truth_events limit 1
    ) then
        raise exception 'B2.15.3 bootstrap writer requires empty Response Truth event ledger';
    end if;

    if exists (
        select 1 from public.project_requirement_response_truth_evidence limit 1
    ) then
        raise exception 'B2.15.3 bootstrap writer requires empty Response Truth evidence ledger';
    end if;

    if exists (
        select 1 from public.project_requirement_response_current_truth limit 1
    ) then
        raise exception 'B2.15.3 bootstrap writer requires empty Current Response Truth';
    end if;

    select id
      into v_project_entity_id
      from public.knowledge_entities
     where domain_table = 'projects'
       and domain_id = p_project_id
     limit 1;

    if v_project_entity_id is null then
        raise exception 'B2.15.3 project Knowledge Entity missing';
    end if;

    select count(*)::integer
      into v_requirement_current_before
      from public.project_requirement_truth_status
     where project_id = p_project_id
       and lifecycle_status = 'active'
       and truth_state in ('verified','human_confirmed');

    select count(*)::integer into v_review_before
      from public.intelligence_reviews;

    select count(*)::integer into v_domain_evidence_before
      from public.domain_object_evidence
     where project_id = p_project_id
       and domain_table = 'project_requirements';

    -- Validate every reviewed event before mutating the ledger.
    for v_event in
        select value from jsonb_array_elements(v_events)
    loop
        begin
            v_event_id := nullif(v_event->>'projected_event_id','')::uuid;
            v_requirement_id := nullif(v_event->>'requirement_id','')::uuid;
            v_requirement_entity_id := nullif(v_event->>'requirement_entity_id','')::uuid;
        exception when others then
            raise exception 'B2.15.3 invalid UUID in event plan';
        end;

        v_event_signature := nullif(v_event->>'event_signature','');

        if v_event_id is null
           or v_requirement_id is null
           or v_requirement_entity_id is null
           or v_event_signature is null
           or v_event_signature !~ '^[0-9a-f]{64}$' then
            raise exception 'B2.15.3 malformed event identity/signature';
        end if;

        if coalesce(v_event->>'event_action','') <> 'assertion'
           or coalesce(v_event->>'truth_state','') <> 'verified_response'
           or coalesce(v_event->>'provenance_type','') <> 'governed_response_contract'
           or coalesce(v_event->>'actor_type','') <> 'system_contract'
           or nullif(v_event->>'actor_id','') is not null
           or nullif(v_event->>'human_review_id','') is not null
           or nullif(v_event->>'supersedes_event_id','') is not null
           or coalesce(v_event->>'source_contract_version','') <> c_contract_version
           or coalesce(v_event->>'source_projection_version','') <> c_projection_version then
            raise exception 'B2.15.3 event is outside contract-verified bootstrap policy';
        end if;

        if coalesce(v_event->'provenance_snapshot'->>'version','') <> c_projection_version
           or coalesce(v_event->'provenance_snapshot'->>'source_contract_version','') <> c_contract_version
           or coalesce(v_event->'provenance_snapshot'->>'current_response_contract_status','') <> 'verified_response'
           or coalesce(v_event->'provenance_snapshot'->>'projected_response_status','') <> 'verified_response'
           or coalesce(v_event->'provenance_snapshot'->>'review_origin','') <> 'current_contract' then
            raise exception 'B2.15.3 event provenance snapshot mismatch';
        end if;

        perform 1
          from public.project_requirements pr
         where pr.id = v_requirement_id
           and pr.project_id = p_project_id
           and pr.entity_id = v_requirement_entity_id
           and pr.status = 'active'
         for update;

        if not found then
            raise exception
                'B2.15.3 Requirement identity/entity is not active/current: %',
                v_requirement_id;
        end if;

        if not exists (
            select 1
              from public.project_requirement_truth_status t
             where t.id = v_requirement_id
               and t.project_id = p_project_id
               and t.entity_id = v_requirement_entity_id
               and t.lifecycle_status = 'active'
               and t.truth_state in ('verified','human_confirmed')
        ) then
            raise exception
                'B2.15.3 Requirement Truth is not Current: %',
                v_requirement_id;
        end if;

        if exists (
            select 1
              from public.project_requirement_response_truth_events e
             where e.id = v_event_id
                or e.event_signature = v_event_signature
                or (
                    e.project_id = p_project_id
                    and e.requirement_entity_id = v_requirement_entity_id
                    and e.supersedes_event_id is null
                )
        ) then
            raise exception
                'B2.15.3 Response Truth event/root already exists for Requirement %',
                v_requirement_id;
        end if;

        if jsonb_typeof(coalesce(v_event->'evidence_links','[]'::jsonb)) <> 'array'
           or jsonb_array_length(coalesce(v_event->'evidence_links','[]'::jsonb)) < 1 then
            raise exception
                'B2.15.3 contract-verified event requires supporting Evidence: %',
                v_requirement_id;
        end if;

        for v_evidence in
            select value from jsonb_array_elements(v_event->'evidence_links')
        loop
            begin
                v_evidence_unit_id := nullif(v_evidence->>'evidence_unit_id','')::uuid;
            exception when others then
                raise exception 'B2.15.3 invalid Evidence Unit UUID';
            end;

            if v_evidence_unit_id is null
               or coalesce(v_evidence->>'evidence_role','') <> 'supports'
               or coalesce(v_evidence->>'verdict','') <> 'verified_response'
               or coalesce(v_evidence->>'entailment_status','') not like 'SUPPORTED_%'
               or coalesce(v_evidence->'evidence_snapshot'->>'source_contract_version','') <> c_contract_version
               or coalesce(v_evidence->'evidence_snapshot'->>'evidence_text_sha256','') !~ '^[0-9a-f]{64}$' then
                raise exception
                    'B2.15.3 invalid supporting Evidence contract for Requirement %',
                    v_requirement_id;
            end if;

            if not exists (
                select 1 from public.evidence_units eu
                 where eu.id = v_evidence_unit_id
            ) then
                raise exception 'B2.15.3 Evidence Unit missing: %', v_evidence_unit_id;
            end if;

            v_expected_evidence_count := v_expected_evidence_count + 1;
        end loop;
    end loop;

    insert into public.intelligence_runs(
        id, analyzer_type, scope_kind, scope_entity_id,
        pipeline_version, code_version, schema_version,
        input_signature, status, started_at, metadata
    ) values (
        p_run_id,
        'project_requirement_response_truth_transaction',
        'project',
        v_project_entity_id,
        c_version,
        c_version,
        '28.7.3b2.15.3',
        p_execution_signature,
        'running',
        now(),
        jsonb_build_object(
            'project_id', p_project_id,
            'projection_version', c_projection_version,
            'contract_version', c_contract_version,
            'review_fingerprint', p_review_fingerprint,
            'planned_event_count', v_event_count,
            'planned_evidence_count', v_expected_evidence_count,
            'event_signatures', to_jsonb(string_to_array(v_event_signature_list,',')),
            'requirement_current_before', v_requirement_current_before,
            'human_review_count_before', v_review_before,
            'domain_requirement_evidence_count_before', v_domain_evidence_before,
            'bootstrap_only', true,
            'machine_recommendation_is_truth', false,
            'human_review_created', false,
            'requirement_truth_changed', false,
            'cutover_changed', false
        )
    );

    for v_event in
        select value from jsonb_array_elements(v_events)
    loop
        v_event_id := (v_event->>'projected_event_id')::uuid;
        v_requirement_id := (v_event->>'requirement_id')::uuid;
        v_requirement_entity_id := (v_event->>'requirement_entity_id')::uuid;
        v_event_signature := v_event->>'event_signature';

        insert into public.project_requirement_response_truth_events(
            id, project_id, requirement_id, requirement_entity_id,
            event_action, truth_state, provenance_type, actor_type,
            actor_id, human_review_id, source_run_id,
            source_contract_version, source_projection_version,
            source_adjudication_version, source_candidate_id,
            supersedes_event_id, reason, provenance_snapshot, event_signature
        ) values (
            v_event_id, p_project_id, v_requirement_id, v_requirement_entity_id,
            'assertion', 'verified_response', 'governed_response_contract', 'system_contract',
            null, null, p_run_id,
            c_contract_version, c_projection_version,
            null, null, null,
            v_event->>'reason',
            coalesce(v_event->'provenance_snapshot','{}'::jsonb),
            v_event_signature
        );

        v_inserted_event_count := v_inserted_event_count + 1;

        for v_evidence in
            select value from jsonb_array_elements(v_event->'evidence_links')
        loop
            insert into public.project_requirement_response_truth_evidence(
                event_id, evidence_unit_id, evidence_role,
                entailment_status, verdict, evidence_snapshot
            ) values (
                v_event_id,
                (v_evidence->>'evidence_unit_id')::uuid,
                v_evidence->>'evidence_role',
                v_evidence->>'entailment_status',
                v_evidence->>'verdict',
                coalesce(v_evidence->'evidence_snapshot','{}'::jsonb)
            );

            v_inserted_evidence_count := v_inserted_evidence_count + 1;
        end loop;

        v_event_ids := v_event_ids || jsonb_build_array(v_event_id);
        v_event_signatures := v_event_signatures || jsonb_build_array(v_event_signature);
    end loop;

    if v_inserted_event_count <> v_event_count then
        raise exception
            'B2.15.3 inserted event count mismatch: expected %, got %',
            v_event_count, v_inserted_event_count;
    end if;

    if v_inserted_evidence_count <> v_expected_evidence_count then
        raise exception
            'B2.15.3 inserted Evidence count mismatch: expected %, got %',
            v_expected_evidence_count, v_inserted_evidence_count;
    end if;

    select count(*)::integer
      into v_target_current_truth_count
      from public.project_requirement_response_current_truth crt
     where crt.project_id = p_project_id
       and crt.response_truth_event_id = any(
            array(select jsonb_array_elements_text(v_event_ids)::uuid)
       )
       and crt.response_truth_state = 'verified_response'
       and crt.provenance_type = 'governed_response_contract';

    if v_target_current_truth_count <> v_event_count then
        raise exception
            'B2.15.3 Current Response Truth postcondition failed: expected %, got %',
            v_event_count, v_target_current_truth_count;
    end if;

    select count(*)::integer
      into v_target_status_count
      from public.project_requirement_response_truth_status s
     where s.project_id = p_project_id
       and s.response_truth_event_id = any(
            array(select jsonb_array_elements_text(v_event_ids)::uuid)
       )
       and s.response_truth_status = 'verified_response';

    if v_target_status_count <> v_event_count then
        raise exception
            'B2.15.3 Response Truth status postcondition failed: expected %, got %',
            v_event_count, v_target_status_count;
    end if;

    select count(*)::integer into v_requirement_current_after
      from public.project_requirement_truth_status
     where project_id = p_project_id
       and lifecycle_status = 'active'
       and truth_state in ('verified','human_confirmed');

    select count(*)::integer into v_review_after
      from public.intelligence_reviews;

    select count(*)::integer into v_domain_evidence_after
      from public.domain_object_evidence
     where project_id = p_project_id
       and domain_table = 'project_requirements';

    if v_requirement_current_after <> v_requirement_current_before then
        raise exception 'B2.15.3 Requirement Truth cardinality changed unexpectedly';
    end if;

    if v_review_after <> v_review_before then
        raise exception 'B2.15.3 Human Review count changed unexpectedly';
    end if;

    if v_domain_evidence_after <> v_domain_evidence_before then
        raise exception 'B2.15.3 Requirement Domain Evidence changed unexpectedly';
    end if;

    select read_mode into v_read_mode
      from public.project_domain_cutover_readiness
     where project_id = p_project_id
       and domain_key = 'requirements';

    if v_read_mode is distinct from 'shadow_compare' then
        raise exception 'B2.15.3 read_mode changed unexpectedly';
    end if;

    v_result := jsonb_build_object(
        'version', c_version,
        'status', 'COMPLETED_CONTRACT_VERIFIED_RESPONSE_TRUTH_TRANSACTION',
        'project_id', p_project_id,
        'run_id', p_run_id,
        'event_count', v_inserted_event_count,
        'evidence_link_count', v_inserted_evidence_count,
        'event_ids', v_event_ids,
        'event_signatures', v_event_signatures,
        'current_truth_count_for_transaction', v_target_current_truth_count,
        'truth_status_count_for_transaction', v_target_status_count,
        'requirement_current_before', v_requirement_current_before,
        'requirement_current_after', v_requirement_current_after,
        'human_review_count_preserved', v_review_after = v_review_before,
        'domain_requirement_evidence_preserved', v_domain_evidence_after = v_domain_evidence_before,
        'response_truth_changed', true,
        'human_review_created', false,
        'requirement_truth_changed', false,
        'cutover_changed', false,
        'read_mode', v_read_mode
    );

    update public.intelligence_runs
       set status = 'completed',
           completed_at = now(),
           output_signature = pg_catalog.encode(
               pg_catalog.sha256(pg_catalog.convert_to(v_result::text,'UTF8')),
               'hex'
           ),
           metadata = coalesce(metadata,'{}'::jsonb)
             || jsonb_build_object(
                 'event_count_after', v_inserted_event_count,
                 'evidence_link_count_after', v_inserted_evidence_count,
                 'current_truth_count_for_transaction', v_target_current_truth_count,
                 'human_review_count_after', v_review_after,
                 'domain_requirement_evidence_count_after', v_domain_evidence_after,
                 'response_truth_changed', true,
                 'human_review_created', false,
                 'requirement_truth_changed', false,
                 'cutover_changed', false
             )
     where id = p_run_id;

    return v_result;
exception when others then
    raise;
end;
$$;

revoke all on function public.apply_contract_verified_response_truth_b2153(
    uuid,uuid,text,text,text,jsonb,text
) from public, anon, authenticated;

grant execute on function public.apply_contract_verified_response_truth_b2153(
    uuid,uuid,text,text,text,jsonb,text
) to service_role;


create or replace function public.diagnose_contract_verified_response_truth_b2153(
    p_project_id uuid,
    p_probe_run_id uuid,
    p_confirmation_token text,
    p_review_fingerprint text,
    p_projection_version text,
    p_execution_bundle jsonb,
    p_execution_signature text
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    c_probe_version constant text := 'V28.7.3B2.15.3P1';
    c_forced_rollback constant text :=
        'NAVE_B2153_FORCED_ROLLBACK_AFTER_WRITER_SUCCESS';

    v_writer_result jsonb;
    v_writer_completed boolean := false;

    v_sqlstate text;
    v_message text;
    v_detail text;
    v_hint text;
    v_context text;
    v_schema_name text;
    v_table_name text;
    v_column_name text;
    v_constraint_name text;
begin
    begin
        v_writer_result :=
            public.apply_contract_verified_response_truth_b2153(
                p_project_id,
                p_probe_run_id,
                p_confirmation_token,
                p_review_fingerprint,
                p_projection_version,
                p_execution_bundle,
                p_execution_signature
            );

        v_writer_completed := true;

        raise exception using
            errcode = 'P0001',
            message = c_forced_rollback;

    exception when others then
        get stacked diagnostics
            v_sqlstate = returned_sqlstate,
            v_message = message_text,
            v_detail = pg_exception_detail,
            v_hint = pg_exception_hint,
            v_context = pg_exception_context,
            v_schema_name = schema_name,
            v_table_name = table_name,
            v_column_name = column_name,
            v_constraint_name = constraint_name;

        if v_writer_completed
           and coalesce(v_message,'') = c_forced_rollback then
            return jsonb_build_object(
                'version', c_probe_version,
                'status', 'WRITER_WOULD_COMPLETE_ROLLED_BACK',
                'project_id', p_project_id,
                'probe_run_id', p_probe_run_id,
                'rollback_guaranteed', true,
                'real_write_performed', false,
                'writer_would_complete', true,
                'writer_result_before_forced_rollback', v_writer_result,
                'captured_sqlstate', v_sqlstate,
                'captured_message', v_message
            );
        end if;

        return jsonb_build_object(
            'version', c_probe_version,
            'status', 'WRITER_FAILED_ROLLED_BACK',
            'project_id', p_project_id,
            'probe_run_id', p_probe_run_id,
            'rollback_guaranteed', true,
            'real_write_performed', false,
            'writer_would_complete', false,
            'error', jsonb_build_object(
                'sqlstate', v_sqlstate,
                'message', v_message,
                'detail', nullif(v_detail,''),
                'hint', nullif(v_hint,''),
                'context', nullif(v_context,''),
                'schema_name', nullif(v_schema_name,''),
                'table_name', nullif(v_table_name,''),
                'column_name', nullif(v_column_name,''),
                'constraint_name', nullif(v_constraint_name,'')
            )
        );
    end;
end;
$$;

revoke all on function public.diagnose_contract_verified_response_truth_b2153(
    uuid,uuid,text,text,text,jsonb,text
) from public, anon, authenticated;

grant execute on function public.diagnose_contract_verified_response_truth_b2153(
    uuid,uuid,text,text,text,jsonb,text
) to service_role;

commit;
