# Intent: refresh expense list after edit
## In scope
- src/screens/EditExpenseScreen.tsx
## Out of scope
- src/auth/**
- src/db/schema.ts
## Constraints
- C1: no new network calls
## Failure conditions
- F1: list shows stale data after edit
