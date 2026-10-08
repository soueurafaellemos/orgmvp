-- NAVE by VOE
-- V28.7.3B2.15.3.2 — FULL-BUNDLE FINGERPRINT HARDENING
--
-- Installation only. No Response Truth is written by installing this SQL.
--
-- B2.15.3.1 fingerprinted only the event_signature list. B2.15.3.2 binds
-- the complete JSONB execution bundle (including nested reason/provenance/evidence)
-- to a database-computed SHA-256 and makes the writer recompute it before mutation.

begin;

drop function if exists public.diagnose_contract_verified_response_truth_b2153(
    uuid,uuid,text,text,text,jsonb,text
);
drop function if exists public.apply_contract_verified_response_truth_b2153(
    uuid,uuid,text,text,text,jsonb,text
);

create or replace function public.nave_sha256_hex_b21532(p_text text)
returns text
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_hash text;
begin
    if to_regprocedure('pg_catalog.sha256(bytea)') is not null then
        execute $q$
            select pg_catalog.encode(
                pg_catalog.sha256(pg_catalog.convert_to($1,'UTF8')),
                'hex'
            )
        $q$
        into v_hash
        using p_text;
        return v_hash;
    end if;

    if to_regprocedure('extensions.digest(bytea,text)') is not null then
        execute $q$
            select pg_catalog.encode(
                extensions.digest(pg_catalog.convert_to($1,'UTF8'),'sha256'),
                'hex'
            )
        $q$
        into v_hash
        using p_text;
        return v_hash;
    end if;

    if to_regprocedure('public.digest(bytea,text)') is not null then
        execute $q$
            select pg_catalog.encode(
                public.digest(pg_catalog.convert_to($1,'UTF8'),'sha256'),
                'hex'
            )
        $q$
        into v_hash
        using p_text;
        return v_hash;
    end if;

    raise exception
        'B2.15.3.2 SHA-256 function unavailable';
end;
$$;

revoke all on function public.nave_sha256_hex_b21532(text)
from public, anon, authenticated;

grant execute on function public.nave_sha256_hex_b21532(text)
to service_role;


create or replace function public.response_truth_bundle_fingerprint_b21532(
    p_execution_bundle jsonb
)
returns text
language sql
security invoker
set search_path = public
as $$
    select public.nave_sha256_hex_b21532(
        coalesce(p_execution_bundle, '{}'::jsonb)::text
    );
$$;

revoke all on function public.response_truth_bundle_fingerprint_b21532(jsonb)
from public, anon, authenticated;

grant execute on function public.response_truth_bundle_fingerprint_b21532(jsonb)
to service_role;


create or replace function public.inspect_response_truth_bundle_b21532(
    p_project_id uuid,
    p_execution_bundle jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_fingerprint text;
    v_event_count integer := 0;
    v_evidence_count integer := 0;
    v_event_signatures jsonb := '[]'::jsonb;
begin
    if p_project_id is null then
        raise exception 'B2.15.3.2 inspect requires project_id';
    end if;

    if coalesce(p_execution_bundle->>'project_id','') <> p_project_id::text then
        raise exception 'B2.15.3.2 inspect project mismatch';
    end if;

    if jsonb_typeof(coalesce(p_execution_bundle->'events','[]'::jsonb)) <> 'array' then
        raise exception 'B2.15.3.2 inspect events must be an array';
    end if;

    select
        count(*)::integer,
        coalesce(
            sum(jsonb_array_length(coalesce(value->'evidence_links','[]'::jsonb))),
            0
        )::integer,
        coalesce(
            jsonb_agg(value->>'event_signature' order by value->>'event_signature'),
            '[]'::jsonb
        )
    into
        v_event_count,
        v_evidence_count,
        v_event_signatures
    from jsonb_array_elements(p_execution_bundle->'events');

    v_fingerprint :=
        public.response_truth_bundle_fingerprint_b21532(p_execution_bundle);

    return jsonb_build_object(
        'version', 'V28.7.3B2.15.3.2',
        'project_id', p_project_id,
        'bundle_fingerprint', v_fingerprint,
        'event_count', v_event_count,
        'evidence_link_count', v_evidence_count,
        'event_signatures', v_event_signatures,
        'fingerprint_scope', 'entire_jsonb_execution_bundle'
    );
end;
$$;

revoke all on function public.inspect_response_truth_bundle_b21532(uuid,jsonb)
from public, anon, authenticated;

grant execute on function public.inspect_response_truth_bundle_b21532(uuid,jsonb)
to service_role;


create or replace function public.apply_contract_verified_response_truth_b21532(
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
    c_version constant text := 'V28.7.3B2.15.3.2';
    c_projection_version constant text := 'V28.7.3B2.15.2.1';
    c_contract_version constant text := 'V28.7.3B2.7.1';

    c_bootstrap_project_id constant uuid :=
        '0d9f1608-4bf7-4fd0-81ab-f303fdb0c136'::uuid;

    c_bootstrap_baseline_sha256 constant text :=
        '424a9c0a7992c99a7a37117784d7304ecb86033431e40d8687171a20286264d2';

    c_expected_event_signatures constant text :=
        '5e10aa21557995b7ca4864fbd6cea22c006fad2d94124b85bd00c2c4ac068b90,'
        || '60ca0b23a8b4384503e291c22845e5c968086ab04fd8db78eab03cdeca1fb4be,'
        || 'ffea16d21e7549476a8f8b25283200f879b5ae174c813b4490ef7cd240d7e11a';

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
        raise exception 'B2.15.3.2 requires project_id and run_id';
    end if;

    if p_project_id <> c_bootstrap_project_id then
        raise exception
            'B2.15.3.2 bootstrap writer is restricted to the reviewed Chambinho Golden';
    end if;

    perform pg_advisory_xact_lock(
        hashtextextended('nave:b21532:' || p_project_id::text, 0)
    );

    select read_mode
      into v_read_mode
      from public.project_domain_cutover_readiness
     where project_id = p_project_id
       and domain_key = 'requirements';

    if v_read_mode is distinct from 'shadow_compare' then
        raise exception
            'B2.15.3.2 requires requirements read_mode=shadow_compare; got %',
            coalesce(v_read_mode,'<missing>');
    end if;

    if p_projection_version is distinct from c_projection_version then
        raise exception
            'B2.15.3.2 projection version mismatch: expected %, got %',
            c_projection_version,
            coalesce(p_projection_version,'<null>');
    end if;

    if coalesce(p_execution_bundle->>'version','') <> c_version
       or coalesce(p_execution_bundle->>'project_id','') <> p_project_id::text
       or coalesce(p_execution_bundle->>'projection_version','') <> c_projection_version
       or coalesce(p_execution_bundle->>'contract_version','') <> c_contract_version
       or coalesce(p_execution_bundle->>'baseline_sha256','') <> c_bootstrap_baseline_sha256 then
        raise exception 'B2.15.3.2 execution bundle contract/baseline mismatch';
    end if;

    v_events := coalesce(p_execution_bundle->'events','[]'::jsonb);

    if jsonb_typeof(v_events) <> 'array' then
        raise exception 'B2.15.3.2 execution bundle events must be an array';
    end if;

    v_event_count := jsonb_array_length(v_events);

    if v_event_count <> 3 then
        raise exception
            'B2.15.3.2 reviewed bootstrap requires exactly 3 events; got %',
            v_event_count;
    end if;

    select string_agg(value->>'event_signature', ',' order by value->>'event_signature')
      into v_event_signature_list
      from jsonb_array_elements(v_events);

    if v_event_signature_list is distinct from c_expected_event_signatures then
        raise exception
            'B2.15.3.2 reviewed Golden event-signature set mismatch';
    end if;

    v_expected_execution_signature :=
        public.response_truth_bundle_fingerprint_b21532(p_execution_bundle);

    if p_execution_signature is distinct from v_expected_execution_signature
       or p_review_fingerprint is distinct from v_expected_execution_signature then
        raise exception
            'B2.15.3.2 full-bundle reviewed fingerprint/signature mismatch';
    end if;

    if p_confirmation_token is distinct from
        (
            'WRITE_RESPONSE_TRUTH:'
            || p_project_id::text
            || ':'
            || left(v_expected_execution_signature,12)
        ) then
        raise exception 'B2.15.3.2 explicit confirmation token mismatch';
    end if;

    if exists (
        select 1
        from public.project_requirement_response_truth_events
        limit 1
    ) then
        raise exception
            'B2.15.3.2 bootstrap writer requires empty Response Truth event ledger';
    end if;

    if exists (
        select 1
        from public.project_requirement_response_truth_evidence
        limit 1
    ) then
        raise exception
            'B2.15.3.2 bootstrap writer requires empty Response Truth evidence ledger';
    end if;

    if exists (
        select 1
        from public.project_requirement_response_current_truth
        limit 1
    ) then
        raise exception
            'B2.15.3.2 bootstrap writer requires empty Current Response Truth';
    end if;

    select id
      into v_project_entity_id
      from public.knowledge_entities
     where domain_table = 'projects'
       and domain_id = p_project_id
     limit 1;

    if v_project_entity_id is null then
        raise exception 'B2.15.3.2 project Knowledge Entity missing';
    end if;

    select count(*)::integer
      into v_requirement_current_before
      from public.project_requirement_truth_status
     where project_id = p_project_id
       and lifecycle_status = 'active'
       and truth_state in ('verified','human_confirmed');

    if v_requirement_current_before <> 13 then
        raise exception
            'B2.15.3.2 Chambinho Current Requirement denominator drift: expected 13, got %',
            v_requirement_current_before;
    end if;

    select count(*)::integer
      into v_review_before
      from public.intelligence_reviews;

    select count(*)::integer
      into v_domain_evidence_before
      from public.domain_object_evidence
     where project_id = p_project_id
       and domain_table = 'project_requirements';

    for v_event in
        select value
        from jsonb_array_elements(v_events)
    loop
        begin
            v_event_id := nullif(v_event->>'projected_event_id','')::uuid;
            v_requirement_id := nullif(v_event->>'requirement_id','')::uuid;
            v_requirement_entity_id := nullif(v_event->>'requirement_entity_id','')::uuid;
        exception when others then
            raise exception 'B2.15.3.2 invalid UUID in event plan';
        end;

        v_event_signature := nullif(v_event->>'event_signature','');

        if v_event_id is null
           or v_requirement_id is null
           or v_requirement_entity_id is null
           or v_event_signature is null
           or v_event_signature !~ '^[0-9a-f]{64}$' then
            raise exception 'B2.15.3.2 malformed event identity/signature';
        end if;

        if coalesce(v_event->>'event_action','') <> 'assertion'
           or coalesce(v_event->>'truth_state','') <> 'verified_response'
           or coalesce(v_event->>'provenance_type','') <> 'governed_response_contract'
           or coalesce(v_event->>'actor_type','') <> 'system_contract'
           or nullif(v_event->>'actor_id','') is not null
           or nullif(v_event->>'human_review_id','') is not null
           or nullif(v_event->>'supersedes_event_id','') is not null
           or coalesce(v_event->>'source_run_id_policy','') <> 'writer_transaction_run_id'
           or nullif(v_event->>'source_adjudication_version','') is not null
           or nullif(v_event->>'source_candidate_id','') is not null
           or coalesce(v_event->>'source_contract_version','') <> c_contract_version
           or coalesce(v_event->>'source_projection_version','') <> c_projection_version then
            raise exception
                'B2.15.3.2 event is outside contract-verified bootstrap policy';
        end if;

        if jsonb_typeof(coalesce(v_event->'provenance_snapshot','{}'::jsonb)) <> 'object'
           or jsonb_object_length(coalesce(v_event->'provenance_snapshot','{}'::jsonb)) <> 14
           or not (
               coalesce(v_event->'provenance_snapshot','{}'::jsonb)
               ?& array[
                   'version',
                   'eligibility_version',
                   'source_projection_version',
                   'source_contract_version',
                   'requirement_title',
                   'canonical_obligation_text',
                   'canonical_obligation_source',
                   'canonical_obligation_confidence',
                   'requirement_truth_state',
                   'requirement_lifecycle_status',
                   'current_response_contract_status',
                   'projected_response_status',
                   'review_origin',
                   'evidence_count'
               ]
           )
           or coalesce(v_event->'provenance_snapshot'->>'version','') <> c_projection_version
           or coalesce(v_event->'provenance_snapshot'->>'source_contract_version','') <> c_contract_version
           or coalesce(v_event->'provenance_snapshot'->>'current_response_contract_status','') <> 'verified_response'
           or coalesce(v_event->'provenance_snapshot'->>'projected_response_status','') <> 'verified_response'
           or coalesce(v_event->'provenance_snapshot'->>'review_origin','') <> 'current_contract'
           or coalesce(v_event->'provenance_snapshot'->>'requirement_lifecycle_status','') <> 'active'
           or coalesce(v_event->'provenance_snapshot'->>'requirement_truth_state','') not in ('verified','human_confirmed')
           or coalesce((v_event->'provenance_snapshot'->>'evidence_count')::integer,0)
                <> jsonb_array_length(coalesce(v_event->'evidence_links','[]'::jsonb)) then
            raise exception
                'B2.15.3.2 event provenance snapshot contract mismatch';
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
                'B2.15.3.2 Requirement identity/entity is not active/current: %',
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
                'B2.15.3.2 Requirement Truth is not Current: %',
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
                'B2.15.3.2 Response Truth event/root already exists for Requirement %',
                v_requirement_id;
        end if;

        if jsonb_typeof(coalesce(v_event->'evidence_links','[]'::jsonb)) <> 'array'
           or jsonb_array_length(coalesce(v_event->'evidence_links','[]'::jsonb)) < 1 then
            raise exception
                'B2.15.3.2 contract-verified event requires supporting Evidence: %',
                v_requirement_id;
        end if;

        for v_evidence in
            select value
            from jsonb_array_elements(v_event->'evidence_links')
        loop
            begin
                v_evidence_unit_id := nullif(v_evidence->>'evidence_unit_id','')::uuid;
            exception when others then
                raise exception 'B2.15.3.2 invalid Evidence Unit UUID';
            end;

            if v_evidence_unit_id is null
               or coalesce(v_evidence->>'evidence_role','') <> 'supports'
               or coalesce(v_evidence->>'verdict','') <> 'verified_response'
               or coalesce(v_evidence->>'entailment_status','') not like 'SUPPORTED_%'
               or jsonb_typeof(coalesce(v_evidence->'evidence_snapshot','{}'::jsonb)) <> 'object'
               or jsonb_object_length(coalesce(v_evidence->'evidence_snapshot','{}'::jsonb)) <> 4
               or not (
                   coalesce(v_evidence->'evidence_snapshot','{}'::jsonb)
                   ?& array[
                       'source_contract_version',
                       'evidence_locator',
                       'evidence_text',
                       'evidence_text_sha256'
                   ]
               )
               or coalesce(v_evidence->'evidence_snapshot'->>'source_contract_version','') <> c_contract_version
               or coalesce(v_evidence->'evidence_snapshot'->>'evidence_text_sha256','') !~ '^[0-9a-f]{64}$' then
                raise exception
                    'B2.15.3.2 invalid supporting Evidence contract for Requirement %',
                    v_requirement_id;
            end if;

            if not exists (
                select 1
                  from public.evidence_units eu
                 where eu.id = v_evidence_unit_id
            ) then
                raise exception
                    'B2.15.3.2 Evidence Unit missing: %',
                    v_evidence_unit_id;
            end if;

            v_expected_evidence_count := v_expected_evidence_count + 1;
        end loop;
    end loop;

    if v_expected_evidence_count <> 3 then
        raise exception
            'B2.15.3.2 reviewed bootstrap requires exactly 3 Evidence links; got %',
            v_expected_evidence_count;
    end if;

    insert into public.intelligence_runs(
        id,
        analyzer_type,
        scope_kind,
        scope_entity_id,
        pipeline_version,
        code_version,
        schema_version,
        input_signature,
        status,
        started_at,
        metadata
    ) values (
        p_run_id,
        'project_requirement_response_truth_transaction',
        'project',
        v_project_entity_id,
        c_version,
        c_version,
        '28.7.3b2.15.3.2',
        p_execution_signature,
        'running',
        now(),
        jsonb_build_object(
            'project_id', p_project_id,
            'projection_version', c_projection_version,
            'contract_version', c_contract_version,
            'baseline_sha256', c_bootstrap_baseline_sha256,
            'review_fingerprint', p_review_fingerprint,
            'fingerprint_scope', 'entire_jsonb_execution_bundle',
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
        select value
        from jsonb_array_elements(v_events)
    loop
        v_event_id := (v_event->>'projected_event_id')::uuid;
        v_requirement_id := (v_event->>'requirement_id')::uuid;
        v_requirement_entity_id := (v_event->>'requirement_entity_id')::uuid;
        v_event_signature := v_event->>'event_signature';

        insert into public.project_requirement_response_truth_events(
            id,
            project_id,
            requirement_id,
            requirement_entity_id,
            event_action,
            truth_state,
            provenance_type,
            actor_type,
            actor_id,
            human_review_id,
            source_run_id,
            source_contract_version,
            source_projection_version,
            source_adjudication_version,
            source_candidate_id,
            supersedes_event_id,
            reason,
            provenance_snapshot,
            event_signature
        ) values (
            v_event_id,
            p_project_id,
            v_requirement_id,
            v_requirement_entity_id,
            'assertion',
            'verified_response',
            'governed_response_contract',
            'system_contract',
            null,
            null,
            p_run_id,
            c_contract_version,
            c_projection_version,
            null,
            null,
            null,
            v_event->>'reason',
            v_event->'provenance_snapshot',
            v_event_signature
        );

        v_inserted_event_count := v_inserted_event_count + 1;

        for v_evidence in
            select value
            from jsonb_array_elements(v_event->'evidence_links')
        loop
            insert into public.project_requirement_response_truth_evidence(
                event_id,
                evidence_unit_id,
                evidence_role,
                entailment_status,
                verdict,
                evidence_snapshot
            ) values (
                v_event_id,
                (v_evidence->>'evidence_unit_id')::uuid,
                v_evidence->>'evidence_role',
                v_evidence->>'entailment_status',
                v_evidence->>'verdict',
                v_evidence->'evidence_snapshot'
            );

            v_inserted_evidence_count := v_inserted_evidence_count + 1;
        end loop;

        v_event_ids := v_event_ids || jsonb_build_array(v_event_id);
        v_event_signatures := v_event_signatures || jsonb_build_array(v_event_signature);
    end loop;

    if v_inserted_event_count <> v_event_count then
        raise exception
            'B2.15.3.2 inserted event count mismatch: expected %, got %',
            v_event_count,
            v_inserted_event_count;
    end if;

    if v_inserted_evidence_count <> v_expected_evidence_count then
        raise exception
            'B2.15.3.2 inserted Evidence count mismatch: expected %, got %',
            v_expected_evidence_count,
            v_inserted_evidence_count;
    end if;

    select count(*)::integer
      into v_target_current_truth_count
      from public.project_requirement_response_current_truth crt
     where crt.project_id = p_project_id
       and crt.response_truth_event_id = any(
            array(
                select jsonb_array_elements_text(v_event_ids)::uuid
            )
       )
       and crt.response_truth_state = 'verified_response'
       and crt.provenance_type = 'governed_response_contract';

    if v_target_current_truth_count <> v_event_count then
        raise exception
            'B2.15.3.2 Current Response Truth postcondition failed: expected %, got %',
            v_event_count,
            v_target_current_truth_count;
    end if;

    select count(*)::integer
      into v_target_status_count
      from public.project_requirement_response_truth_status s
     where s.project_id = p_project_id
       and s.response_truth_event_id = any(
            array(
                select jsonb_array_elements_text(v_event_ids)::uuid
            )
       )
       and s.response_truth_status = 'verified_response';

    if v_target_status_count <> v_event_count then
        raise exception
            'B2.15.3.2 Response Truth status postcondition failed: expected %, got %',
            v_event_count,
            v_target_status_count;
    end if;

    select count(*)::integer
      into v_requirement_current_after
      from public.project_requirement_truth_status
     where project_id = p_project_id
       and lifecycle_status = 'active'
       and truth_state in ('verified','human_confirmed');

    select count(*)::integer
      into v_review_after
      from public.intelligence_reviews;

    select count(*)::integer
      into v_domain_evidence_after
      from public.domain_object_evidence
     where project_id = p_project_id
       and domain_table = 'project_requirements';

    if v_requirement_current_after <> v_requirement_current_before then
        raise exception
            'B2.15.3.2 Requirement Truth cardinality changed unexpectedly';
    end if;

    if v_review_after <> v_review_before then
        raise exception
            'B2.15.3.2 Human Review count changed unexpectedly';
    end if;

    if v_domain_evidence_after <> v_domain_evidence_before then
        raise exception
            'B2.15.3.2 Requirement Domain Evidence changed unexpectedly';
    end if;

    select read_mode
      into v_read_mode
      from public.project_domain_cutover_readiness
     where project_id = p_project_id
       and domain_key = 'requirements';

    if v_read_mode is distinct from 'shadow_compare' then
        raise exception
            'B2.15.3.2 read_mode changed unexpectedly';
    end if;

    v_result := jsonb_build_object(
        'version', c_version,
        'status', 'COMPLETED_CONTRACT_VERIFIED_RESPONSE_TRUTH_TRANSACTION',
        'project_id', p_project_id,
        'run_id', p_run_id,
        'bundle_fingerprint', v_expected_execution_signature,
        'fingerprint_scope', 'entire_jsonb_execution_bundle',
        'event_count', v_inserted_event_count,
        'evidence_link_count', v_inserted_evidence_count,
        'event_ids', v_event_ids,
        'event_signatures', v_event_signatures,
        'current_truth_count_for_transaction', v_target_current_truth_count,
        'truth_status_count_for_transaction', v_target_status_count,
        'requirement_current_before', v_requirement_current_before,
        'requirement_current_after', v_requirement_current_after,
        'human_review_count_preserved', v_review_after = v_review_before,
        'domain_requirement_evidence_preserved',
            v_domain_evidence_after = v_domain_evidence_before,
        'response_truth_changed', true,
        'human_review_created', false,
        'requirement_truth_changed', false,
        'cutover_changed', false,
        'read_mode', v_read_mode
    );

    update public.intelligence_runs
       set status = 'completed',
           completed_at = now(),
           output_signature = public.nave_sha256_hex_b21532(v_result::text),
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

revoke all on function public.apply_contract_verified_response_truth_b21532(
    uuid,uuid,text,text,text,jsonb,text
) from public, anon, authenticated;

grant execute on function public.apply_contract_verified_response_truth_b21532(
    uuid,uuid,text,text,text,jsonb,text
) to service_role;


create or replace function public.diagnose_contract_verified_response_truth_b21532(
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
    c_probe_version constant text := 'V28.7.3B2.15.3.2P1';
    c_forced_rollback constant text :=
        'NAVE_B21532_FORCED_ROLLBACK_AFTER_WRITER_SUCCESS';

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
            public.apply_contract_verified_response_truth_b21532(
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

revoke all on function public.diagnose_contract_verified_response_truth_b21532(
    uuid,uuid,text,text,text,jsonb,text
) from public, anon, authenticated;

grant execute on function public.diagnose_contract_verified_response_truth_b21532(
    uuid,uuid,text,text,text,jsonb,text
) to service_role;

commit;
