# Banking microservices — graded test prompts

Six services for the AgentIA generator, graded against the envelopes the repo already uses
(`backend/tests/fixtures/graded_blueprints/MANIFEST.md`), so "simple / medium / hard" maps
to something measurable rather than to a feeling.

| Level | Tier | Entities | Attributes/entity | Stories | Scenarios | Operations | Relationships |
|---|---|---|---|---|---|---|---|
| Simple | 1 | 1 | 3–5 | 1–2 | 2–3 | create + read | none |
| Simple | 2 | 2 | 4–6 | 2–3 | 4–6 | create + read | exactly one FK |
| Medium | 3 | 3–4 | 6–10 | 3–5 | 6–12 | **full CRUD** | child-of-child, one validation-heavy entity |
| Hard | 4 | 5–7 | 6–14 (one at 10–14) | 6–8 | 12–20 | CRUD + collection reads | **depth ≥ 3 hops**, plus one trap |

## What each prompt actually contains

Measured from the prompts below, not asserted:

| Prompt | Tier | Entities | Attributes (total) | Widest entity | Foreign keys |
|---|---|---|---|---|---|
| `savings-account-service` | 1 | 1 | 5 | 5 | 0 |
| `customer-account-service` | 2 | 2 | 10 | 5 | 1 |
| `loan-servicing-service` | 3 | 4 | 25 | 10 | 3 |
| `card-issuing-service` | 3 | 4 | 29 | 8 | 3 |
| `wire-transfer-service` | 4 · cross-aggregate | 6 | 35 | 10 | 6 |
| `core-ledger-service` | 4 · type breadth | 6 | 42 | 14 | 6 |
| `payment-processing-service` | 4 · nested names | 7 | 42 | 12 | 6 |

Entity count, foreign-key count and the widest entity all sit inside the envelope for the
tier each claims.

**One deliberate deviation.** The envelope states 6–10 attributes *per entity* from tier 3
up; the lookup entities here are smaller (`Collateral` 4, `Customer` 4, `Beneficiary` 5,
`Currency` 5). Padding them to six would mean inventing filler fields, and filler fields
give the generator more to get right for no additional signal — they make a worse test, not
a harder one. The measures that carry the difficulty are the **widest** entity, the total,
the foreign-key count and the shape of the rules, and those are the ones listed above.

---

**How to run one.** *Nuevo Microservicio* → paste the prompt → confirm the header badge reads
**DEEPSEEK** (on `mock` the prompt is ignored and you get the fixed sample). Cost is
5 model calls per session, about **$0.05–0.06** on DeepSeek; each run takes 3–4 minutes.

**Why the unhappy paths are spelled out in every prompt.** Explicit 4xx/404/empty-collection
behaviour is the part a generator usually gets wrong — the same tell that made the
helpdesk service useful as a test. A prompt whose only criteria are happy paths measures
very little.

---

## SIMPLE

### S1 · `savings-account-service` — tier 1

```
A savings account registry for a retail bank branch.

Entity:
- SavingsAccount: id (Long, generated), accountNumber (String, required, 8 to 20
  characters), holderName (String, required), balance (BigDecimal, required, may not
  be negative), openedAt (LocalDateTime, required)

Rules:
- Registering an account returns it with its generated identifier.
- Reading an account that does not exist returns 404.
- Reading all accounts returns a collection, empty when none exist.

Provide the JPA entity, repository, service, controller and tests.
```

**Checks:** one entity, no relationship, no declared validation beyond required. Read the
account back by id. `balance` must be `BigDecimal` (a `Double` here is a real defect — money).

### S2 · `customer-account-service` — tier 2

```
A retail banking service linking customers to their accounts.

Entities:
- Customer: id (Long, generated), taxId (String, required, unique),
  fullName (String, required), email (String, required, well-formed email address),
  segment (String, required, one of RETAIL, PREMIUM, PRIVATE)
- BankAccount: id (Long, generated), iban (String, required, unique),
  currency (String, required, ISO code), balance (BigDecimal, required),
  customerId (Long, required, references Customer.id)

Rules:
- A bank account belongs to exactly one customer, and the customer identifier is stored
  on the account as a foreign key.
- Registering a customer with a malformed email returns 400 before reaching the service
  layer.
- Opening an account for a customer that does not exist returns 404.
- Listing the accounts of a customer that has none returns 200 with an EMPTY array,
  not a 404.
- Registering two customers with the same taxId returns 400.

Provide the full CRUD for both, a read that lists the accounts of one customer, JPA
entities, repositories, services, controllers and JUnit tests.
```

**Checks:** the FK is a real relationship (`@ManyToOne`), not a bare `Long`. Two unique
constraints. The empty-collection rule is the classic trap — 404 is the easy wrong answer.

---

## MEDIUM

### M1 · `loan-servicing-service` — tier 3

```
A loan servicing service for a commercial bank.

Entities:
- Borrower: id (Long, generated), taxId (String, required, unique),
  legalName (String, required), email (String, required, valid email),
  creditRating (String, required, one of A, B, C, D)
- LoanAccount: id (Long, generated), loanReference (String, required, unique),
  principal (BigDecimal, required, greater than zero), annualRate (BigDecimal,
  required, between 0 and 40), termMonths (Integer, required, 1 to 480),
  status (String, required, one of PENDING, ACTIVE, SETTLED, DEFAULTED),
  disbursedAt (LocalDate, optional), maturityDate (LocalDate, optional),
  daysPastDue (Integer, required, zero or more),
  borrowerId (Long, required, references Borrower.id)
- RepaymentSchedule: id (Long, generated), installmentNumber (Integer, required),
  dueDate (LocalDate, required), amountDue (BigDecimal, required),
  amountPaid (BigDecimal, required), loanAccountId (Long, required, references
  LoanAccount.id)
- Collateral: id (Long, generated), collateralType (String, required),
  appraisedValue (BigDecimal, required), loanAccountId (Long, required, references
  LoanAccount.id)

Rules:
- Full CRUD on all four entities.
- LoanAccount has a foreign key to Borrower; RepaymentSchedule and Collateral each have a
  foreign key to LoanAccount. A schedule belongs to a loan, and a loan belongs to a
  borrower: RepaymentSchedule -> LoanAccount -> Borrower.
- Creating a loan with principal zero or negative returns 400.
- Creating a loan with annualRate above 40 returns 400.
- Updating a loan to status SETTLED is allowed; updating it to an unknown status returns 400.
- Deleting a borrower that still has loans returns 409 rather than orphaning them.
- Listing the schedules of a loan that has none returns 200 with an EMPTY array.
- Listing the loans of a borrower returns only that borrower's loans.

Provide JPA entities, repositories, services, controllers and JUnit tests.
```

**Checks:** four entities, **full CRUD** (update and delete appear for the first time), a
child-of-child chain, and one validation-heavy entity. The `daysPastDue` + `status`
combination is the interesting part — a status transition only `update` can express.
`409` on the delete is a rule most generators skip.

### M2 · `card-issuing-service` — tier 3, second shape

```
A payment card issuing and authorisation service.

Entities:
- Cardholder: id (Long, generated), taxId (String, required, unique),
  fullName (String, required), email (String, required, valid email),
  phoneNumber (String, optional), registeredAt (LocalDateTime, required)
- Card: id (Long, generated), pan (String, required, unique, 16 digits),
  cardType (String, required, one of DEBIT, CREDIT, PREPAID),
  status (String, required, one of ACTIVE, BLOCKED, EXPIRED),
  creditLimit (BigDecimal, required), expiryDate (LocalDate, required),
  issuedAt (LocalDateTime, required), cardholderId (Long, required, references
  Cardholder.id)
- Merchant: id (Long, generated), merchantCode (String, required, unique),
  legalName (String, required), categoryCode (String, required),
  countryCode (String, required, two letters), settlementCurrency (String, required),
  isActive (Boolean, required)
- CardTransaction: id (Long, generated), transactionReference (String, required,
  unique), amount (BigDecimal, required, greater than zero), currency (String,
  required), status (String, required, one of AUTHORISED, DECLINED, SETTLED),
  occurredAt (LocalDateTime, required), cardId (Long, required, references Card.id),
  merchantId (Long, required, references Merchant.id)

Rules:
- Full CRUD on all four entities.
- CardTransaction has TWO foreign keys: to Card and to Merchant.
- Authorising a transaction on a card that is not ACTIVE returns 409.
- Authorising a transaction above the card's creditLimit returns 409.
- Authorising a transaction for an unknown card returns 404.
- Listing the transactions of a card returns them most recent first, and returns 200 with
  an EMPTY array when there are none.

Provide JPA entities, repositories, services, controllers and JUnit tests.
```

**Checks:** two foreign keys on one child (the "two FKs on one child" step), plus
business rules that need the *parent* loaded — authorising needs the Card to check its
status and limit. That is where a generator typically puts logic in the controller.

---

## HARD

Each hard prompt carries **one trap axis**, matching how the existing tier-4 corpus is
built. The trap is the point: a hard service without one is just a large service.

### H1 · `wire-transfer-service` — trap: cross-aggregate invariant

```
An interbank wire transfer service.

Entities:
- Bank: id (Long, generated), bic (String, required, unique, 8 or 11 characters),
  name (String, required), countryCode (String, required, two letters),
  cutoverHour (Integer, required, 0 to 23)
- SettlementAccount: id (Long, generated), accountNumber (String, required, unique),
  currency (String, required), availableBalance (BigDecimal, required),
  bankId (Long, required, references Bank.id)
- Customer: id (Long, generated), taxId (String, required, unique),
  legalName (String, required), email (String, required, valid email)
- Beneficiary: id (Long, generated), name (String, required),
  accountNumber (String, required), bankBic (String, required),
  customerId (Long, required, references Customer.id)
- TransferInstruction: id (Long, generated), instructionReference (String, required,
  unique), amount (BigDecimal, required, greater than zero), currency (String,
  required), valueDate (LocalDate, required), status (String, required, one of
  DRAFT, SUBMITTED, SETTLED, REJECTED), submittedAt (LocalDateTime, optional),
  settlementAccountId (Long, required, references SettlementAccount.id),
  beneficiaryId (Long, required, references Beneficiary.id),
  customerId (Long, required, references Customer.id)
- TransferAmendment: id (Long, generated), fieldChanged (String, required),
  previousValue (String, optional), newValue (String, required),
  amendedAt (LocalDateTime, required), transferInstructionId (Long, required,
  references TransferInstruction.id)

Rules:
- Full CRUD on all six entities.
- Submitting a transfer is valid only relative to several aggregates at once: the
  settlement account must have availableBalance at least the transfer amount, the
  transfer currency must equal the settlement account currency, and the submission must
  occur before the cutover hour of the bank that owns the settlement account. This rule
  needs the transfer, its settlement account and that account's bank loaded together.
- Submitting a transfer whose settlement account has insufficient balance returns 409.
- Submitting a transfer in a currency that differs from its settlement account returns 409.
- Submitting a transfer for a settlement account belonging to a bank whose cutover hour
  has passed returns 409.
- Listing the amendments of a transfer returns 200 with an EMPTY array when there are none.
- Deleting a transfer that has amendments returns 409.

Provide JPA entities, repositories, services, controllers and JUnit tests.
```

**The trap:** the invariant spans **three** aggregates and cannot live in the controller or
in one service call. A generator that puts it in the controller, or calls its own HTTP
endpoints to fetch the bank, is doing it wrong. Depth is 4 hops:
`TransferAmendment → TransferInstruction → SettlementAccount → Bank`.

### H2 · `core-ledger-service` — trap: type-mapping breadth

```
A core banking ledger posting service.

Entities:
- LedgerAccount: id (Long, generated), accountNumber (String, required, unique),
  accountName (String, required), accountType (String, required, one of ASSET,
  LIABILITY, EQUITY, INCOME, EXPENSE), openedOn (LocalDate, required),
  isActive (Boolean, required)
- CostCentre: id (Long, generated), code (String, required, unique),
  description (String, required), ownerEmail (String, required, valid email),
  createdAt (Instant, required)
- Currency: id (Long, generated), isoCode (String, required, unique),
  minorUnits (Integer, required, 0 to 4), symbol (String, required),
  isActive (Boolean, required)
- LedgerEntry: id (Long, generated), entryReference (UUID, required, unique),
  postedAt (Instant, required), valueDate (LocalDate, required),
  narrative (String, required), debitAmount (BigDecimal, required),
  creditAmount (BigDecimal, required), exchangeRate (Double, required),
  quantity (Integer, required), isReversed (Boolean, required),
  tags (List<String>, optional),
  ledgerAccountId (Long, required, references
  LedgerAccount.id), costCentreId (Long, required, references CostCentre.id),
  currencyId (Long, required, references Currency.id)
- PostingBatch: id (Long, generated), batchReference (String, required, unique),
  openedAt (Instant, required), closedAt (Instant, optional), entryCount (Integer,
  required), status (String, required, one of OPEN, CLOSED, FAILED),
  costCentreId (Long, required, references CostCentre.id)
- BatchMembership: id (Long, generated), addedAt (Instant, required),
  sequenceNumber (Integer, required), postingBatchId (Long, required, references
  PostingBatch.id), ledgerEntryId (Long, required, references LedgerEntry.id)

Rules:
- Full CRUD on all six entities.
- LedgerEntry has three foreign keys and spans every type family in use: UUID, Instant,
  LocalDate, BigDecimal for money, Double for rates and tolerances, Integer, Boolean,
  String and List<String>. Keep those types distinct; do not collapse Double into
  BigDecimal or LocalDate into LocalDateTime.
- Posting a LedgerEntry where debitAmount and creditAmount are both zero returns 400.
- Posting an entry to an inactive ledger account returns 409.
- Reversing an entry that is already reversed returns 409.
- Listing the entries of a posting batch returns 200 with an EMPTY array when there are none.
- Deleting a ledger account that has entries returns 409.

Provide JPA entities, repositories, services, controllers and JUnit tests.
```

**The trap:** a 14-attribute entity using every type family, with `BigDecimal`/`Double` and
`LocalDate`/`LocalDateTime`/`Instant` pairs that map to different SQL columns. It tempts
collapsing types — and collapsing money onto `Double` is the failure that matters.

### H3 · `payment-processing-service` — trap: nested names / layering

```
A payment processing service.

Entities:
- Customer: id (Long, generated), taxId (String, required, unique),
  legalName (String, required), email (String, required, valid email)
- PaymentAccount: id (Long, generated), accountNumber (String, required, unique),
  currency (String, required), balance (BigDecimal, required),
  customerId (Long, required, references Customer.id)
- Payment: id (Long, generated), paymentReference (String, required, unique),
  amount (BigDecimal, required, greater than zero), currency (String, required),
  status (String, required, one of CREATED, VALIDATED, SENT, FAILED),
  description (String, optional), feeAmount (BigDecimal, required),
  exchangeRate (Double, required), createdAt (LocalDateTime, required),
  settledAt (LocalDateTime, optional), isUrgent (Boolean, required),
  paymentAccountId (Long, required, references PaymentAccount.id)
- PaymentInstruction: id (Long, generated), instructionType (String, required, one of
  IMMEDIATE, SCHEDULED, STANDING_ORDER), requestedDate (LocalDate, required),
  executedAt (LocalDateTime, optional), paymentId (Long, required, references
  Payment.id)
- PaymentInstructionAmendment: id (Long, generated), amendedField (String, required),
  previousValue (String, optional), newValue (String, required),
  amendedAt (LocalDateTime, required), paymentInstructionId (Long, required,
  references PaymentInstruction.id)
- PaymentAudit: id (Long, generated), action (String, required),
  actor (String, required), occurredAt (LocalDateTime, required),
  paymentId (Long, required, references Payment.id)
- PaymentFee: id (Long, generated), feeType (String, required),
  amount (BigDecimal, required), chargedAt (LocalDateTime, required),
  paymentId (Long, required, references Payment.id)

Rules:
- Full CRUD on all seven entities, and emit ONE controller, ONE service and ONE
  repository per entity. Do not create a single controller for all Payment-prefixed
  entities, and do not inject one service into another to reach a repository.
- A payment is created against a payment account; an instruction belongs to a payment;
  an amendment belongs to an instruction. PaymentInstructionAmendment -> PaymentInstruction
  -> Payment -> PaymentAccount.
- Creating a payment whose amount exceeds its account balance returns 409.
- Creating an instruction for a payment that is not in status CREATED returns 409.
- Amending an instruction records the previous and new value.
- Listing the amendments of an instruction returns 200 with an EMPTY array when there are
  none.
- Listing the fees of a payment returns them ordered by chargedAt.
- Deleting an account that has payments returns 409.

Provide JPA entities, repositories, services, controllers and JUnit tests.
```

**The trap:** four entities share the `Payment` prefix. The lazy structural answer is one
controller per prefix, or a service injected into a service instead of one repository per
entity. Seven entities and depth 4 also make this the largest of the three.

---

## What to check on every run, regardless of level

| # | Check | Why it matters |
|---|---|---|
| 1 | **Sandbox verdict** — VERIFIED / BLOCKED / SKIPPED | The only reliability number that counts. Record it per run. |
| 2 | **Stage requests** — 5 stages × 1 = 5 calls? | More means a stage spent its correction budget. |
| 3 | **`schema.sql` creates every entity's table** | Under `ddl-auto=none` nothing else creates them, and a mismatch means the service cannot start. |
| 4 | **Money is `BigDecimal`** | `Double` for currency is a real defect, not a style choice. |
| 5 | **`@MockBean`, not `@MockitoBean`** | The latter does not exist in the pinned Spring Boot 3.2.3. |
| 6 | **No `@NotNull` on a generated `@Id`** | Hibernate's pre-insert validation rejects every insert otherwise. |
| 7 | **The empty-collection rule returns 200 `[]`** | The classic wrong answer is 404. |
| 8 | **Every declared failure path has a test** | A service that only tests happy paths proves very little. |

**Suggested order:** S1 → S2 → M1 → H1 → H2 → H3. Run each twice before drawing a
conclusion: a single VERIFIED session is an anecdote, and every measurement in this repo's
history has been a proportion over repeated runs for that reason.

**Note on what these measure.** The generated tests are written by the generator and run
against its own output, so a green build means "the code does what its own tests say".
Whether the service implements the specified rules is a separate question — the one the
independent acceptance layer would answer, and the reason item 8 above is on the list.
