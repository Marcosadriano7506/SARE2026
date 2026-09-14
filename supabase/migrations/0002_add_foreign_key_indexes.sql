create index ix_class_applications_finalized_by on public.class_applications(finalized_by);
create index ix_class_applications_reopened_by on public.class_applications(reopened_by);
create index ix_discursive_uploads_uploaded_by on public.discursive_uploads(uploaded_by);
create index ix_student_records_saved_by on public.student_records(saved_by);
