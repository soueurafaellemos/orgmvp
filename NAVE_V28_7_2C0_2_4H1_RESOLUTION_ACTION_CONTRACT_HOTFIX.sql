-- NAVE by VOE · V28.7.2C0.2.4H1
-- Resolution Action Contract Hotfix
--
-- Fixes the DB/runtime contract introduced by C0.2.4 role precision.
-- The C0.2.4 Python runtime emits explicit no-domain resolution actions such as
-- preserve_context / preserve_suggestion / preserve_example / attach_parameter.
-- The previous DB CHECK still accepted only the older C0 vocabulary.
--
-- Incremental and non-destructive. No data cleanup, no Graph rebuild, no cutover.

begin;

alter table public.semantic_observations
  drop constraint if exists semantic_observations_resolution_action_check;

alter table public.semantic_observations
  add constraint semantic_observations_resolution_action_check
  check (resolution_action in (
    -- A / shared historical vocabulary
    'none',
    'attach_occurrence',
    'create_instance',
    'review_required',
    'no_domain_object',
    'insufficient_evidence',
    'reconcile_domain_object',

    -- Requirement identity / occurrence vocabulary
    'create_requirement',
    'attach_requirement_occurrence',
    'attach_scope',
    'attach_attribute',
    'attach_constraint',

    -- C0.2.4 role-precision vocabulary
    'preserve_context',
    'preserve_reference',
    'preserve_suggestion',
    'preserve_example',
    'attach_parameter',
    'attach_constraint_qualifier'
  ));

notify pgrst, 'reload schema';

commit;

select
  'V28.7.2C0.2.4H1 installed'::text as status,
  exists (
    select 1
    from pg_constraint c
    join pg_class r on r.oid=c.conrelid
    join pg_namespace n on n.oid=r.relnamespace
    where n.nspname='public'
      and r.relname='semantic_observations'
      and c.conname='semantic_observations_resolution_action_check'
  ) as resolution_action_contract_ok,
  to_regclass('public.project_requirement_reconciliation_status') is not null as status_view_ok;
