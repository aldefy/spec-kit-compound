# Plan
Fix src/screens/EditExpenseScreen.tsx. While investigating, found the same
swallowed-save bug in EditCompletedSessionScreen.

requested_surface:
  files: [src/screens/EditCompletedSessionScreen.tsx]
  reason: identical onSaved() omission causes the same stale-list failure
  risk_class: behavioral
  bounded_by: F1
