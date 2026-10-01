-- NAVE by VOE
-- V28.7.3B2.12.5.3 — Rollback-Only Transaction Probe
--
-- INCIDENT DIAGNOSTIC ONLY.
--
-- Purpose:
-- - execute the exact B2.12.5.1 writer path inside a PL/pgSQL subtransaction;
-- - capture the original PostgreSQL SQLSTATE/message/detail/hint/context;
-- - force rollback even if the writer WOULD succeed;
-- - return diagnostic data without persisting any Requirement/Truth/Evidence changes.
--
-- This function never authorizes a real supersession.

begin;

create or replace function public.diagnose_project_requirement_identity_supersession_b21253(
  p_project_id uuid,
  p_probe_run_id uuid,
  p_confirmation_token text,
  p_review_fingerprint text,
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
  c_version constant text := 'V28.7.3B2.12.5.3';
  c_forced_rollback_message constant text :=
    'NAVE_B21253_FORCED_ROLLBACK_AFTER_WRITER_SUCCESS';

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
  if p_project_id is null or p_probe_run_id is null then
    raise exception 'B2.12.5.3 requires project_id and probe_run_id';
  end if;

  /*
   * BEGIN ... EXCEPTION creates a PostgreSQL subtransaction.
   *
   * Every mutation performed by the called B2.12.5.1 writer belongs to this
   * subtransaction. If the writer raises, PostgreSQL rolls the subtransaction
   * back before entering EXCEPTION. If the writer returns successfully, this
   * probe intentionally raises c_forced_rollback_message so the successful
   * writer path is also rolled back before we return.
   */
  begin
    v_writer_result :=
      public.apply_project_requirement_identity_supersession_b2125(
        p_project_id,
        p_probe_run_id,
        p_confirmation_token,
        p_review_fingerprint,
        p_pipeline_promotion_version,
        p_execution_bundle,
        p_execution_signature
      );

    v_writer_completed := true;

    raise exception using
      errcode = 'P0001',
      message = c_forced_rollback_message;

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
       and coalesce(v_message,'') = c_forced_rollback_message then
      return jsonb_build_object(
        'version', c_version,
        'status', 'WRITER_WOULD_COMPLETE_ROLLED_BACK',
        'project_id', p_project_id,
        'probe_run_id', p_probe_run_id,
        'review_fingerprint', p_review_fingerprint,
        'rollback_guaranteed', true,
        'real_write_performed', false,
        'writer_would_complete', true,
        'writer_result_before_forced_rollback', v_writer_result,
        'captured_sqlstate', v_sqlstate,
        'captured_message', v_message
      );
    end if;

    return jsonb_build_object(
      'version', c_version,
      'status', 'WRITER_FAILED_ROLLED_BACK',
      'project_id', p_project_id,
      'probe_run_id', p_probe_run_id,
      'review_fingerprint', p_review_fingerprint,
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

comment on function public.diagnose_project_requirement_identity_supersession_b21253(
  uuid,uuid,text,text,text,jsonb,text
) is
  'V28.7.3B2.12.5.3 — rollback-only diagnostic wrapper around B2.12.5.1. Captures PostgreSQL diagnostics and forces rollback on both failure and success paths.';

revoke all on function public.diagnose_project_requirement_identity_supersession_b21253(
  uuid,uuid,text,text,text,jsonb,text
) from public, anon, authenticated;

grant execute on function public.diagnose_project_requirement_identity_supersession_b21253(
  uuid,uuid,text,text,text,jsonb,text
) to service_role;

commit;
