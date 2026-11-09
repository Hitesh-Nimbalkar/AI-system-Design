# Kubernetes Operators — CRDs + Controllers as Automation (Day 40)

> Source: Day 40 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: **Operators** — what they are, why stateful workloads need them, how they differ from Helm/Kustomize, maturity levels, how they're built, and a full demo of the **kube-green** operator.
> Prerequisite: **Day 39** (CRs, CRDs, custom controllers), Day 07 (controllers), Day 14 (StatefulSets previewed).
> Next: **Pod security** — Day 41.

---

## 1) Sixty-Second Recap of Day 39

| Concept | Meaning |
|---|---|
| **Default resources** | Ship with Kubernetes (`kubectl api-resources` on a vanilla cluster) |
| **Custom resources** | You (or a tool) define them — Kubernetes is extensible |
| **CRD** | The **template/schema** for a custom resource |
| **CR** | An **instance** of that CRD — a developer's **intent** |
| **Custom controller** | Runs a **control loop**: observe desired state → compare with current → **reconcile** |

> **The key lesson from Day 39:** *"Just creating a CRD and a CR will not do anything until and unless we have a controller that is constantly watching this CR."*

**The Day 39 demo** built a `BackupPolicy` CRD with `schedule`, `retentionDays`, `targetPVC` — and **nothing happened**, because no controller existed.

> **Day 40 is what happens when you add the controller — and package the whole thing.**

---

## 2) Why Operators? The Deployment Story Is Easy

> *"Deploying applications on Kubernetes is relatively straightforward."*

You can ship an app several ways:

| Method | What it gives you |
|---|---|
| **Raw manifests** | You apply every object yourself |
| **Helm charts** | *"A one-click option to implement your entire application"* — templating + packaging |
| **Kustomize** | Overlay-based customization of manifests |

> All three are **packaging/deployment** tools. They get the app **installed**.

### But these applications need more than installation

| Category | Examples |
|---|---|
| **Databases** | **PostgreSQL**, **MySQL**, **Cassandra** — relational and non-relational |
| **Message brokers** | **Kafka**, **RabbitMQ** — "your middleware" |
| **Monitoring** | **Prometheus**, **Thanos**, **New Relic** |

> *"Stateful and complex applications… require **far more than just installation**."*

They need **day-2 operations**: replication, failover, backups, upgrades, scaling, recovery. That's the gap operators fill.

---

## 3) Stateless vs Stateful — the Concept

### The three tiers (Day 11)

```
Web tier          ← the user interacts with this
Application tier  ← business logic ("backend")
Data tier         ← storage; everything lives here
```

Each tier can be a single codebase **or** split into microservices. A tier can be **stateless** or **stateful**, independently.

### Stateless

> **A stateless component stores no data within itself.** It holds **code/logic only**.

- **Web tier stateless** → only frontend logic.
- **Application tier stateless** → only business logic; **no data, no caching of its own**.

### Stateful

> **The data tier is typically stateful** — it's the tier that **holds the data**.

### The session example (why this matters)

Varun visits a site, logs in, chooses **preferred language** and **currency**. That's **session information**, and it lives **in the pod** — if the web tier is stateful.

```
Pod 1 knows: Varun, English, INR
Pod 1 dies 💀
        │
        ▼
Pod 2 takes over: "Who are you?"
```

> **The user has to redo everything** — language, currency, preferences. *"Not the experience Varun expects from a good application."*

### The fix: externalise the session

Add a **cache/session store** — e.g. **Amazon ElastiCache** (or any Redis/Memcached, or a cloud-native equivalent):

```
Varun ──► Web tier (pod 1 or pod 2 — doesn't matter)
              │
              ▼
        Session store: { user: varun, lang: en, currency: INR, ... }
```

> **Now the session survives pod death**, and the web tier becomes **truly stateless**. Pod 2 reads the session from the store.

**What's actually in "session information":**

- Which site referred the user
- Active promotions
- Preferred language, currency, theme (dark/light), location

> **The principle: outsource everything. Your tiers/microservices should hold only application logic.**

### Modern apps cache at the application tier too

> *"Modern applications do not rely on databases for everything."*

```
Application tier ──► cache (recently accessed data)
        │
        └──► database (only on a cache miss)
```

**The cache is extremely fast**, and the DB is queried only when the data isn't cached. (Any cache works — cloud-native or third-party.)

---

## 4) Deploying a Stateful Workload Is Genuinely Hard

### Databases cannot use Deployments

> **In a Deployment, every pod is identical — that's why they're called replicas.**

But a database is **not** a set of replicas:

```
master  ──replicate──►  mirror-1  ──replicate──►  mirror-2
```

`mirror-1` and `mirror-2` are **mirrors of the master**, not interchangeable copies. **Designed, not replicated.**

### What you must design

| Requirement | Why |
|---|---|
| **Master, then mirror-1, then mirror-2** | A deliberate topology |
| **What tooling replicates master→mirror-1**, and mirror-1→mirror-2 | Not a Kubernetes concern |
| **Stable pod names/identity** | A client connects to a *specific* database node — **a load-balancing ClusterIP Service is wrong here** |
| **Ordered startup** | `mirror-2` is useless if master and `mirror-1` aren't up — **no simultaneous start** |

> *"I do not want to distribute the load. Hence I want **consistent identities**. … I want these pods to start **in sequence**."*

**That's what StatefulSets are for** (a later lecture) — stable identity + ordered creation + per-pod storage.

### The human cost — two roles, dozens of tasks

| **DevOps engineer** | **DBA** |
|---|---|
| Provision volumes | Design **replication topology** |
| Configure **StatefulSets** | Configure **replication parameters** |
| Set up **headless Service** | Manage **failover & promotion** |
| Bootstrap **replication logic** | Define **backup/restore strategy** |
| Add **liveness/readiness/init containers** | Tune **performance parameters** |
| Manage **Secrets, ConfigMaps, RBAC** | Ensure **replication consistency** |
| Schedule **backups** (CronJobs) | |
| **Monitor** the database | |
| Implement **custom failover logic** | |

> **Even if you automate part of this, a lot remains.** And: *"How can we ensure there will be no human errors?"*

That's the seam where operators enter.

---

## 5) What Is a Kubernetes Operator?

> **A design pattern for managing complex — often stateful or operationally heavy — applications by codifying domain-specific knowledge into a custom controller that runs inside the cluster.**

The key phrase: **codifying domain-specific knowledge**. A DBA's expertise about *"how to run Postgres safely"* becomes **code**.

### The framing that makes it click

```
Before:  human operators (DevOps + DBA) doing config → operations → monitoring
After:   a Kubernetes operator doing it — continuously, identically, without fatigue
```

> *"Whatever tasks were performed by human operators are given to the Kubernetes operator."*

### It's a *logical construct* — built from parts you already know

> *"If you understood CRDs, CRs and custom controllers, then a Kubernetes operator is a cakewalk — it's just a logical construct. There are components within the operator that ensure it does what it's supposed to."*

| Component | Role |
|---|---|
| **CRD** | **Extends the Kubernetes API** with a new resource type — the **template** |
| **Custom Resource (CR)** | An **instance** created by the user to **express intent** |
| **Custom controller** | The **logic** — replication, backups, failover, lifecycle |
| **Built-in resources** | Deployments, Services, ServiceAccounts, RBAC, NetworkPolicies the operator **creates and manages** |

### "Intent" is the word to hold onto

Day 39's backup CR expressed intent: *"back up at this time, retain this long, target this PVC."*

An operator CR expresses bigger intent:

> *"Run backups every night."* · *"Deploy a three-node DB cluster."*

**One object → the operator builds and maintains everything underneath.**

### What an operator does end-to-end

| Capability | Meaning |
|---|---|
| **Coordinated scaling & upgrades** | Scale/upgrade members in the right order |
| **Backup & restore orchestration** | Schedule, execute, verify |
| **Health checks & self-healing** | Detect and repair |
| **Failover automation** | Promote a mirror when the master dies |
| **Observability integrations** | Export metrics/traces |
| **Full lifecycle ownership** | Install → operate → upgrade → recover |

> *"Whatever you can think of, an operator can do — **as long as you can write the logic for it**."*

### Why built-in resources count as a component

> An operator usually **creates default resources**: a monitoring operator might create **Deployments**, a **ServiceAccount** (needed for any tool talking to the API — Day 37), RBAC, NetworkPolicies, Services.

> **Think of an operator as an automation engine**, not as "a CRD." It orchestrates **both** custom and built-in resources.

---

## 6) OperatorHub — Where Operators Live

> **operatorhub.io** is the catalogue.

Search and you'll find operators for: **MySQL**, **PostgreSQL**, **Prometheus**, **Kyverno**, **Argo CD**, and most complex software.

**What installing one gives you:**

```
1. The operator itself (a Deployment, usually)
2. Its CRDs     ← created for you
3. Its controller
4. The default resources it needs (ServiceAccount, RBAC, Services…)
```

> That's why *"deploy Prometheus with one click"* works: the **Prometheus Operator** brings the CRDs, the controller, and the built-in resources Prometheus needs.

---

## 7) Operators Are Not Just for Databases

> *"Do not limit your imagination. Operators are a **general-purpose automation pattern**."*

| Domain | Why an operator |
|---|---|
| **Prometheus** | **Too many moving parts** to deploy by hand — *"time-consuming and error-prone"* |
| **Security / TLS** | cert-manager, **Kyverno** |
| **Networking** | CNI and gateway components ship operators |
| **CI/CD** | **Argo CD** has an operator |
| **Your own apps** | Internal applications, **SaaS integrations**, company-specific logic |

> **If a piece of software is bundled with an operator, that bundle *is* how you're meant to run it.**

---

## 8) Helm vs Kustomize vs Operators

The obvious objection: *"I can deploy Prometheus with a Helm chart — why operators?"*

### The answer: **nothing is watching**

> *"If you deploy something via Helm or Kustomize, **it is just deployed**. No one is monitoring it. No one is ensuring the desired state matches the current state."*

| | **Helm / Kustomize** | **Operator** |
|---|---|---|
| **Purpose** | **Templating / packaging** — get it installed | **Lifecycle management** — keep it running |
| **Ongoing monitoring** | ❌ none after install | ✅ **continuous** |
| **Drift correction** | ❌ | ✅ delete a Service → **recreated** |
| **Upgrades** | You run the upgrade | **Automated, coordinated** |
| **Backups / failover / reconfig** | ❌ | ✅ |
| **Scaling** | You change the values | **Automated, topology-aware** |
| **Health reconciliation** | ❌ | ✅ desired vs current, continuously |

> *"If someone walks into your cluster and deletes your Service — ideally nobody should — the operator will ensure it's recreated."*

### They're complementary, not competitors

> **You can deploy an operator using Helm.** Helm **templatizes**; the operator **operates**.

| Combination | Result |
|---|---|
| Helm alone | Installed once, then unmanaged |
| Operator alone | Fully managed, but you write the install YAML by hand |
| **Helm + Operator** | **"Extremely powerful"** — packaged install *and* lifecycle management |

> **The functions don't overlap:** *"The function Helm is doing cannot be performed by operators, and vice versa."*

---

## 9) Maturity Levels — Primitive vs Advanced

The Day 39 backup example **is** an operator: CRD + controller + CR.

```
CRD: BackupPolicy
CR:  schedule / retentionDays / targetPVC
Controller: takes the backup on schedule
```

> *"Anything that has a custom controller can still be called an operator — the difference is the **maturity level**."*

### What a production-grade backup operator must *also* do

| Category | Capabilities |
|---|---|
| **Migration** | Migrate **legacy backups** |
| **Restore** | Trigger restores **safely**; **compatibility validation** before restoring |
| **Reliability** | **Retry failed jobs with backoff**; clean **orphaned resources**; handle **concurrency and race conditions** |
| **Observability** | Integrate with **Prometheus** — metrics, alerts |

> **DevOps = continuous improvement, and it applies to operators too.** The primitive version works; the advanced version is **trustworthy under failure**.

### Why this distinction is practical

If you build your own operator, *"it could take time to reach the state everyone on your team desires."* Knowing the maturity ladder keeps expectations honest — and it's why **off-the-shelf operators from OperatorHub are so valuable**: they've already climbed it.

---

## 10) How Are Operators Built?

| Approach | When |
|---|---|
| **Go + Operator SDK** | **Strong business logic** — *"nothing can beat a programming language"* |
| **Helm-based operator** | You're comfortable with Helm |
| **Ansible-based operator** | You're comfortable with Ansible |

> *"Most of the Kubernetes default controllers — the **Deployment controller**, the **StatefulSet controller** — are also written in Go."*

**How to choose:** if you know **all three**, pick **Go** — with Go your operator can be **more powerful**.

> *"If you want to create a Go operator, you can use the **Operator SDK**."*

---

## 11) Demo — The **kube-green** Operator

### What it does

> **Scales workloads down to zero during hours you specify**, then back up again.

It works on anything that uses pods under the hood: **Deployments, StatefulSets, CronJobs**.

**Target workloads:** non-production — **dev, UAT, QA** (anything that shouldn't run 24×7).

### Why an organisation wants it

| Benefit | Mechanism |
|---|---|
| **Cost optimization** | Fewer pods → **fewer nodes** → lower bill |
| **Sustainability** | Lower **CO₂ footprint** (kube-green publishes figures) |

> This is the "FinOps + green IT" pitch — and it's a **real production-useful** operator, not a toy.

### Step 1 — Install OLM (Operator Lifecycle Manager)

> **OLM is to operators what Homebrew is to packages on a Mac.** It manages operator installation and lifecycle.

Installing OLM creates a **lot**:

| Created | Type |
|---|---|
| Namespaces (`olm`, `operators`) | Built-in |
| ~8 **CRDs** | Cluster-scoped |
| **Deployments** (3 in `olm`) | Built-in |
| ClusterRoles / ClusterRoleBindings / ServiceAccounts | Built-in |
| **NetworkPolicies** | Built-in |

> **Notice what this proves:** OLM is *itself* an operator-like thing — it brings **CRDs + a controller + built-in resources**. Exactly the four components from Section 5.

> **It takes 10–15 minutes.** Plan for it.

```bash
kubectl get deploy -A            # 3 deployments in the olm namespace
kubectl get ns                   # olm, operators, …
kubectl get crd                  # ~8 new CRDs
```

### Step 2 — Install the kube-green operator

```bash
kubectl apply -f https://.../kube-green.yaml     # an OLM Subscription
```

> The installation references the **`olm` namespace** — this is an **OLM-managed** operator install, not a bare Deployment.

After it settles:

```bash
kubectl get crd | Select-String sleep
# sleepinfos.kube-green.com
```

**A new type appeared:**

```bash
kubectl api-resources | Select-String sleep
# sleepinfos   ...   kube-green.com/v1alpha1   true   SleepInfo
```

> **`v1alpha1`** — remember Day 39's versioning lifecycle. This operator's API is **alpha**: usable, but not frozen.

### Step 3 — Read the schema

```bash
kubectl get crd sleepinfos.kube-green.com -o yaml > test.yaml
```

> Exactly like Day 39: the CRD tells you **what a valid `SleepInfo` looks like**. Reading the CRD is how you learn a new operator's API **without** reading its docs.

### Step 4 — A workload to sleep

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 2
  # ...
```

```bash
kubectl apply -f 01-app.yaml
kubectl get deploy           # nginx   2/2
kubectl get pods             # 2 pods
```

> **A normal, healthy nginx Deployment with 2 replicas** — the thing we're about to put to sleep.

### Step 5 — The `SleepInfo` custom resource

```yaml
apiVersion: kube-green.com/v1alpha1
kind: SleepInfo
metadata:
  name: sleepinfo-sample
  labels:
    app: kube-green
spec:
  excludeRef:
    - apiVersion: apps/v1
      kind: Deployment
      name: critical-apps         # never sleep this one
  sleepAt: "2000"                 # 20:00 — 8 p.m.
  wakeUpAt: "0800"                # 08:00 — 8 a.m.
  timeZone: Asia/Kolkata          # you're in India
  weekdays: "1-5"                 # Mon–Fri (or every day, per your need)
  suspendCronJobs: true
```

### Reading it — **this is the "intent"**

| Field | Meaning |
|---|---|
| **`excludeRef`** | A **Deployment to leave alone** — e.g. `critical-apps` in production must run 24×7 |
| **`sleepAt: "2000"`** | Scale down at **20:00** |
| **`wakeUpAt: "0800"`** | Scale back up at **08:00** |
| **`timeZone`** | **`Asia/Kolkata`** — schedules are timezone-aware |
| **`weekdays`** | Which days the schedule applies |
| **`suspendCronJobs`** | Also **suspend CronJobs** while asleep |

> **Compare with Day 39's `BackupPolicy`:** same shape — a small declarative intent object. The difference is that **this one has a controller that acts**.

> **The documentation is the source of truth** for the full option set; read it for every field.

### Step 6 — Watch it work

To avoid waiting until 8 p.m., set `sleepAt` a few minutes ahead (the lecture used **10:26** for a 10:21 clock):

```bash
kubectl apply -f 02-sleepinfo.yaml
kubectl get pods -w
kubectl get deploy -w
```

```
nginx   2/2   ...    ← 10:21
...
nginx   0/2   ...    ← 10:26 — SCALED TO ZERO
```

**Proof in `describe`:**

```bash
kubectl describe deployment nginx
# Events: ... Scaled down replica set nginx-xxxxx to 0 from 2
```

### Step 7 — Find the controller

```bash
kubectl get pods -A | Select-String kube-green
# kube-green-controller-manager-xxxxx   Running   operators namespace
```

> **The controller runs in the `operators` namespace** and is watching **your** `nginx` Deployment — because the `SleepInfo` said *"everything except `critical-apps`."*

```
SleepInfo CR (intent: sleep at 20:00, exclude critical-apps)
        │
        ▼
kube-green controller (Deployment in `operators` ns)
        │
        ├── sees nginx: not excluded → scale to 0 ✅
        └── sees critical-apps: excluded → leave alone
```

> **The whole loop, closed:** CRD (schema) → CR (intent) → controller (action). Everything from Day 39, producing a **real, observable change**.

---

## 12) Key Takeaways

1. **An operator is a design pattern**: complex/stateful app management, with **domain expertise codified into a custom controller** that runs in-cluster.
2. **Operators = CRD + CR(s) + custom controller**, often **plus built-in resources** (Deployments, ServiceAccounts, RBAC, NetworkPolicies).
3. **Deploying is easy** (manifests, Helm, Kustomize). **Operating is hard** — that's the operator's domain.
4. **Stateless = stores no data**; **stateful = holds data**. A component (not just an app) can be either.
5. **Sessions in pods are fragile** — pod dies, user loses language/currency/preferences. **Externalise to a cache** (ElastiCache/Redis) → **truly stateless**.
6. **Modern apps cache at the application tier** and only hit the DB on a miss.
7. **Databases can't use Deployments** — their pods are **not interchangeable replicas**; they're **master + mirrors** with **distinct identities**.
8. **A ClusterIP Service is wrong for a database** — it load-balances; databases need **consistent identity** and **ordered startup** (master → mirror-1 → mirror-2).
9. **The human workload is huge** — DevOps (StatefulSets, headless Services, volumes, probes, secrets, backups, monitoring, failover) **plus** DBA (topology, replication params, promotion, restore strategy, tuning, consistency).
10. **Operators exist to eliminate human error and toil** in exactly that space.
11. **The operator's core components**: CRD (**template**), CR (**intent**), controller (**logic**), built-in resources (**the things it manages**).
12. **Intent is the API**: *"run backups nightly"*, *"deploy a three-node DB cluster"* — one object, everything else derived.
13. **Operator capabilities:** coordinated scaling/upgrades, backup/restore, health checks, self-healing, failover, observability.
14. **OperatorHub** is the catalogue — MySQL, Postgres, Prometheus, Kyverno, Argo CD, and hundreds more.
15. **Operators are general-purpose**, not database-only. Consider one for any complex packaged software.
16. **Helm/Kustomize template and install; operators operate.** Helm does **not** monitor or reconcile — an operator **continuously** does.
17. **Delete a managed Service and the operator recreates it** — that's the drift-correction difference.
18. **Combine them:** deploy the operator **with** Helm; get packaging **and** lifecycle management.
19. **Maturity matters**: primitive backup operator = schedule/retain; **advanced** = restore safety, compatibility checks, retries with backoff, orphan cleanup, race handling, Prometheus integration.
20. **Build with Go + Operator SDK** for real logic; Helm/Ansible-based operators exist for simpler cases. **Kubernetes' own controllers are Go.**
21. **OLM is the package manager for operators** — and is itself operator-shaped (CRDs + controller + built-ins). It takes **10–15 minutes** and creates **two namespaces** plus ~8 CRDs.
22. **kube-green** scales Deployments/StatefulSets/CronJobs **to zero** outside business hours — **cost + CO₂** savings for dev/UAT/QA.
23. **`SleepInfo` CR** fields: `sleepAt`, `wakeUpAt`, `timeZone`, `weekdays`, `excludeRef`, `suspendCronJobs`.
24. **Read the CRD to learn a new operator's API** — the schema *is* the documentation for valid inputs.

---

## 13) Essential Commands

```bash
# --- Browse operators ---
#   operatorhub.io  → search MySQL / Postgres / Prometheus / Kyverno / Argo CD

# --- Install OLM (takes 10-15 min) ---
#   follow the operatorhub / kube-green install instructions
kubectl get ns                                   # olm, operators, ...
kubectl get deploy -A                             # olm's deployments
kubectl get crd                                   # CRDs OLM brought in

# --- Install the operator ---
kubectl apply -f https://.../kube-green.yaml
kubectl get crd | Select-String sleep             # sleepinfos.kube-green.com
kubectl api-resources | Select-String sleep       # SleepInfo, kube-green.com/v1alpha1

# --- Learn its schema (Day 39 technique) ---
kubectl get crd sleepinfos.kube-green.com -o yaml > test.yaml
kubectl explain sleepinfo                          # also works

# --- Deploy a workload to sleep ---
kubectl apply -f 01-app.yaml
kubectl get deploy
kubectl get pods

# --- Create the intent ---
kubectl apply -f 02-sleepinfo.yaml
kubectl get sleepinfo
kubectl describe sleepinfo sleepinfo-sample

# --- Watch the operator act ---
kubectl get pods -w
kubectl get deploy -w
kubectl describe deployment nginx                  # "Scaled down replica set ... to 0 from 2"

# --- Find the controller ---
kubectl get pods -A | Select-String kube-green
kubectl get deploy -n operators
```

### The `SleepInfo` resource

```yaml
apiVersion: kube-green.com/v1alpha1
kind: SleepInfo
metadata:
  name: sleepinfo-sample
  labels:
    app: kube-green
spec:
  excludeRef:
    - apiVersion: apps/v1
      kind: Deployment
      name: critical-apps
  sleepAt: "2000"
  wakeUpAt: "0800"
  timeZone: Asia/Kolkata
  weekdays: "1-5"
  suspendCronJobs: true
```

### The four components, on one slide

```
CRD          sleepinfos.kube-green.com        ← the template / schema
CR           SleepInfo/sleepinfo-sample       ← the intent
Controller   kube-green-controller-manager    ← the logic (Deployment)
Built-ins    Deployments scaled to 0, CronJobs suspended, RBAC/SA…
```

---

## 14) Quick Self-Check

1. What does an operator add that a CRD alone does not?
2. Define stateless and stateful. Can a *component* be stateful while the app overall is stateless?
3. Explain the session problem: what breaks when a stateful web-tier pod dies?
4. What does externalising sessions to a cache fix, and what does it make the web tier?
5. Why do modern applications cache at the application tier rather than always hitting the DB?
6. Why can't a database be deployed as a normal Deployment?
7. Why is a load-balancing ClusterIP Service wrong for a database, and what do you need instead?
8. Why must database pods start in order?
9. List four DevOps and four DBA responsibilities for running a database.
10. Define a Kubernetes operator in one sentence. Which phrase makes it more than a controller?
11. Name the four components of an operator and one line each.
12. What does "CRs express intent" mean? Give two examples from the lecture.
13. Why are built-in resources (Deployments, SAs) part of an operator's story?
14. What can an operator do that a Helm chart cannot? Give three specifics.
15. Why can't an operator replace Helm's role, and vice versa?
16. What's the difference between a primitive and an advanced backup operator? Name four advanced capabilities.
17. Which language is used for serious operators, and which SDK?
18. Why is OLM described as a package manager? What does installing it create?
19. What does kube-green do, and which workloads does it target?
20. Which `SleepInfo` fields control the schedule, and what does `excludeRef` protect?
21. In the demo, how did you *prove* the operator acted — which command showed what?
22. What does `v1alpha1` in `kube-green.com/v1alpha1` tell you about the API's stability?
23. How can you learn a new operator's valid inputs **without** reading its documentation?

---

## What's Next (Day 41)

- **Pod security** — security contexts, Pod Security Standards/Admission, and how to lock down what a container can do. *"With great power comes great responsibility."*

---

*End of Day 40 notes.*
