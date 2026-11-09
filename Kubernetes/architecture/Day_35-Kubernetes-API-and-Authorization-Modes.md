# The Kubernetes API & Authorization Modes — RBAC, ABAC, Webhook, Node (Day 35)

> Source: Day 35 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: What the **Kubernetes API** actually is (vs the API server), its **endpoints and API groups**, and every **authorization mode** — **RBAC, ABAC, Webhook, Node, AlwaysAllow/AlwaysDeny** — including how they **combine**.
> Prerequisite: Day 07 (API server as hub), Day 14 (namespaces), Day 33 (`--client-ca-file` and static pod manifests), Day 34 (authentication with certificates).
> Next: **RBAC deep dive**.

---

## 1) Kubernetes API ≠ API Server

This distinction is the lecture's opening move, and it's the one people get wrong.

| | **API server** | **Kubernetes API** |
|---|---|---|
| What | A **physical component** — runs as a container or VM | A **logical construct** hosted *inside* it |
| Role | The central hub, entry point to the cluster | The **interface** — an umbrella of endpoints |
| Scope | Does **many** jobs | Is **one** of those jobs |

### The API server has multiple responsibilities

- **Authentication**
- **Authorization**
- **Admission control** (later in the course)
- **Schema validation**
- **Hosting the Kubernetes API** ← this lecture's subject
- …and more

> *"Hosting the Kubernetes API is **one** of the functionalities of the API server."*
> So: the Kubernetes API is **logically hosted in** the API server.

### The analogy

The API server is a **reception desk** in a building. The Kubernetes API is the **directory of services** posted behind that desk — every request is routed through reception, but reception is not the directory.

---

## 2) The Kubernetes API Is RESTful

> **REST** (Representational State Transfer) is a set of **principles**. Any system adhering to them is **RESTful**.

The principle that matters here:

> **HTTP verbs operate on resources.**
>
> `GET`, `POST`, `PUT`, `PATCH`, `DELETE` → applied to `pods`, `deployments`, `serviceaccounts`, …

### "Who converts `kubectl get pods` into REST?"

> **The `kubectl` CLI.**

```
Seema types:              kubectl get pods
                              │
kubectl translates ───────────┘
                              ▼
REST call:  GET https://<api-server>:6443/api/v1/namespaces/default/pods
                              │
                              ▼
API server: authenticates → authorizes → routes to the right endpoint
```

The CLI exists **for humans**. The API server only understands REST. `kubectl` is the translator — and that's why anything else (CI/CD, dashboards, `curl`) speaks REST directly.

---

## 3) The Endpoints

The Kubernetes API is an **umbrella term** for several endpoint families.

| Endpoint | Purpose | Auth required? |
|---|---|---|
| **`/version`** | The **API server's** version | ❌ **public** |
| **`/healthz`**, **`/livez`**, **`/readyz`** | **Health** of the API server — each returns `ok` when healthy | ❌ **public** |
| **`/api`** | **Core** API group — `v1` | ✅ (for resources) |
| **`/apis`** | **Named** API groups | ✅ (for resources) |
| **`/metrics`** | API server metrics in **Prometheus** format | ✅ **requires authentication** |
| **`/logs`** | API server logs — **not** an official endpoint | ✅ (and only with flags enabled) |

### The "funky Z" question

`/healthz`, `/livez`, `/readyz` end in a **Z** because Kubernetes may later introduce **resources** named `health` or `ready`. The trailing `z` prevents a **name collision** between an endpoint and a resource path.

> Small detail, but the lecture's reasoning is worth keeping: **path namespaces are shared**, so endpoints get defensive names.

### Which endpoints are "public"?

The colour coding in the lecture means:

| Colour | Meaning |
|---|---|
| **Yellow** | **No authentication needed** — `/version`, `/healthz`, `/livez`, `/readyz` |
| **Green** | The **resource** endpoints — `/api` and `/apis` — where all your objects live |
| **Pink** | `/metrics` — needs auth, but is its own thing |
| **Red** | `/logs` — **not** a standard standalone API endpoint |

### `/logs` — the one to be careful about

> **Do not confuse `/logs` with `kubectl logs`.**

| | What it does |
|---|---|
| **`curl /logs`** | Returns the **API server's own logs** — and only when specific flags are enabled. Not officially a standard API endpoint; you'll see it in informal discussions |
| **`kubectl logs <pod>`** | Fetches a **pod's** logs — and that request is served by the **kubelet**, not by this endpoint |

---

## 4) Hands-On — Hitting the API with `curl`

### Step 1 — Find the API server address

```bash
kubectl config view
```

```yaml
clusters:
  - name: kind-my-second-cluster
    cluster:
      server: https://127.0.0.1:53856     # ← here
```

### Step 2 — Try `/version` without TLS verification

```bash
curl -k https://127.0.0.1:53856/version
```

> **Why the `-k`?** Without it: **`SSL certificate problem`**. Your **laptop** does not have the Kubernetes CA certificate, so it cannot verify the API server's certificate (Day 31/32). `-k` **skips verification** — fine for a lab, **never** for production.

Result:

```json
{ "major": "1", "minor": "31", "gitVersion": "v1.31.4", ... }
```

> Cross-check: `kubectl get nodes` reports the same version — the client and server versions should line up (within skew limits).

### Step 3 — Health endpoints need no credentials

```bash
curl -k https://127.0.0.1:53856/readyz     # ok
curl -k https://127.0.0.1:53856/livez      # ok
curl -k https://127.0.0.1:53856/healthz    # ok
```

**No certificate, no token** — and they answer. That's the "yellow" category: **public by design**, so load balancers and probes can check the control plane.

### Step 4 — `/metrics` refuses you

```bash
curl -k https://127.0.0.1:53856/metrics
```

```
403 Forbidden
```

> **Authentication is now required.** Anonymous access gets a hard no — which is the correct default for anything that leaks cluster internals.

### Step 5 — Authenticating `curl` properly (and why we won't)

```bash
curl --help all | Select-String certificate
```

You can pass `--cert`, `--key`, `--cacert` — all extractable from your kubeconfig. It **works**, but it's tedious: extract base64, decode to files, remember which of the three certs is which.

> *"I do not want to go to the hassle of providing certificate information. Is there another way?"* → yes.

---

## 5) `kubectl proxy` — the Shortcut

```bash
kubectl proxy
# Starting to serve on 127.0.0.1:8001
```

### What it does

> Starts a **local HTTP proxy server** on `127.0.0.1:8001`.

| Leg | Protocol | Credentials |
|---|---|---|
| **Your `curl` → `kubectl proxy`** | **plain HTTP** (localhost only) | none needed |
| **`kubectl proxy` → API server** | **HTTPS** | **from your kubeconfig** |

**So why is plain HTTP acceptable here?** Because:

1. Traffic never leaves **localhost** (loopback, not the network).
2. The proxy wraps it in **HTTPS** on the way to the API server.
3. The proxy **reads your kubeconfig** — that's how it authenticates. `curl` alone has no way to look at a kubeconfig; `kubectl proxy` does, because it *is* `kubectl`.

> **This is the key insight:** you're borrowing `kubectl`'s identity and TLS setup for arbitrary HTTP requests.

### Now everything works

```bash
curl http://127.0.0.1:8001/metrics          # ✅ full Prometheus metrics
curl http://127.0.0.1:8001/logs             # 404 page not found (flags not enabled)
curl http://127.0.0.1:8001/version          # ✅ still works
curl http://127.0.0.1:8001/api/v1/namespaces/default/pods   # ✅ the live pod list
```

### `kubectl proxy` ≠ `kube-proxy` — do not mix these up

| | **`kubectl proxy`** | **`kube-proxy`** |
|---|---|---|
| Type | **A `kubectl` subcommand** you run locally | **A data-plane component** |
| Runs as | A local process on your machine | A **DaemonSet**, one pod per node |
| Job | **HTTP→HTTPS proxy** to the API server | **Service-to-pod networking**, traffic direction |
| Scope | Your workstation | Every node |

> Same-sounding names, nothing else in common. This trip-up is common enough that it's worth a flashcard.

---

## 6) API Groups — Core vs Named

The Kubernetes API is organised into **groups**, for one practical reason: **there are a lot of resource types**, and they need orderly namespaces.

```
/api      → CORE group      (v1 only — no group name in the path)
/apis     → NAMED groups    (/apis/<group>/<version>)
```

### Why core has no name

> **Kubernetes started with only the core group.** When named groups were introduced, they added the group segment to the path — but the core group **kept its original shape** for **backwards compatibility**.

| | **Core group** | **Named group** |
|---|---|---|
| Path | `/api/v1` | `/apis/<group>/<version>` |
| Group segment | **none** | **present** |
| `apiVersion` in YAML | **`v1`** | **`apps/v1`**, `batch/v1`, … |
| Contents | **Primitive, original** objects | **Everything newer** |
| Examples | `pods`, `services`, `pv`, `pvc`, `replicationcontrollers`, `configmaps`, `secrets`, `serviceaccounts` | `deployments`, `daemonsets`, `statefulsets`, `jobs`, `cronjobs`, `roles`, `clusterroles`, `storageclasses`, `certificatesigningrequests` |

### Why grouping is genuinely useful

Look at `kubectl api-resources` and the group column tells you **what domain** a resource belongs to:

| Group | Contains |
|---|---|
| **(core)** `v1` | pods, services, configmaps, secrets, pv/pvc, serviceaccounts |
| **`apps/v1`** | deployments, daemonsets, statefulsets, replicasets |
| **`batch/v1`** | **jobs, cronjobs** |
| **`rbac.authorization.k8s.io/v1`** | roles, rolebindings, clusterroles, clusterrolebindings |
| **`storage.k8s.io/v1`** | storageclasses, csidrivers, volumeattachments |
| **`networking.k8s.io/v1`** | ingresses, networkpolicies |
| **`certificates.k8s.io/v1`** | **certificatesigningrequests** (Day 34) |
| **`authentication.k8s.io` / `authorization.k8s.io`** | token reviews, subject access reviews |

> **The `apiVersion` you write in YAML is exactly `<group>/<version>`** — or just `<version>` when the group is **core** (empty). That's why `apiGroups: [""]` in an RBAC rule means "core": an **empty string** stands for the nameless core group.

### "Why not move everything into named groups?"

> **Backwards compatibility — a conscious decision.** Anything present from the beginning stays in core; anything new goes into a named group. Moving `pods` into a group would break **every manifest and every client** ever written.

---

## 7) The API Path Syntax

```
/{root}/{group}/{version}/namespaces/{namespace}/{resource}/{name}
```

The **group** segment is **optional** — present for named groups, absent for core.

### Example — a **namespaced, core** resource

```
/api/v1/namespaces/default/pods
   ▲   ▲   ▲          ▲       ▲
   │   │   │          │       └── resource type
   │   │   │          └────────── namespace
   │   │   └───────────────────── version
   │   └───────────────────────── (no group — core!)
   └───────────────────────────── root
```

`curl http://127.0.0.1:8001/api/v1/namespaces/default/pods` → the pods in `default`, matching `kubectl get pods`.

### Example — a **namespaced, named-group** resource

```
/apis/apps/v1/namespaces/default/deployments
      ▲    ▲  ▲          ▲          ▲
      │    │  │          │          └── resource
      │    │  │          └───────────── namespace
      │    │  └──────────────────────── version
      │    └─────────────────────────── group  ← present now
      └──────────────────────────────── root for named groups
```

### Example — a **cluster-scoped** resource (no namespace segment!)

```
/apis/rbac.authorization.k8s.io/v1/clusterroles
```

> Notice: **no `namespaces/...` part** — because `clusterroles` are cluster-wide. This is exactly the `NAMESPACED: false` column from `kubectl api-resources`.

---

## 8) Authentication vs Authorization

> **Authentication** verifies **who you are**. **Authorization** determines **what you're allowed to do**.

### Who can authenticate?

| Identity type | Notes |
|---|---|
| **Users** | Humans — their identity comes from a certificate CN (Day 34) or a token |
| **Groups** | Collections of users (cert `O=` field) |
| **ServiceAccounts** | Identities for **workloads** (covered later in the course) |

### What authorization answers

> *"If someone has the `create pods` permission, they can create **pods** — and nothing else."*

**Authentication = the door. Authorization = which rooms you may enter.** Day 34 demonstrated this literally: Seema authenticated fine and was still `Forbidden`.

---

## 9) The Authorization Modes

| Mode | Status | Who configures | Notes |
|---|---|---|---|
| **RBAC** | **99% of clusters** | You | Role-based; the default answer |
| **ABAC** | **Deprecated** | You (static JSON) | Requires API server **restart** per change |
| **Webhook** | Common in regulated environments | You (config file) | Outsources to **OPA/Gatekeeper** |
| **Node** | **Always on** | *Nobody* — built in | Lets kubelets work |
| **AlwaysAllow** | Never in production | You | "Anyone authenticated can do anything" |
| **AlwaysDeny** | Rare (lockdown) | You | Blocks everything |

> *"99% is my own statistic"* — from the instructor's operational experience. Almost every cluster he has worked with used **RBAC**; about 1% used **RBAC + Webhook**; he has **never** seen **ABAC** in a production cluster.

---

### RBAC — Role-Based Access Control

> **Defines WHO (user, group, or service account) can perform WHAT actions on WHICH resources.**

Example: *"Seema can only **read** data about **pods**."*

That's it — **(subject, verb, resource)**. It is **role-based**, not attribute-based: you attach permissions to roles, then bind roles to identities.

**Key objects:**

| Object | Scope | Purpose |
|---|---|---|
| **Role** | Namespace | Permissions **within one namespace** |
| **RoleBinding** | Namespace | Binds a Role (or ClusterRole) to a subject, **within one namespace** |
| **ClusterRole** | Cluster | Permissions **cluster-wide** |
| **ClusterRoleBinding** | Cluster | Binds a ClusterRole to a subject, **cluster-wide** |
| ⚠️ **RoleBinding** *(correction)* | Namespace | *(The slide list omitted this one — it's essential.)* |

### The misconception worth killing now

> *"A ClusterRole can't be used for namespaced resources like Deployments."* — **False.**

- A **ClusterRole** may absolutely contain `deployments`, `pods`, etc.
- Bind it with a **ClusterRoleBinding** → the user gets that access **in every namespace**.
- Bind it with a **RoleBinding** → the user gets that access **only in that RoleBinding's namespace**.

| Want | Use |
|---|---|
| Pods in **one** namespace | **Role** + RoleBinding |
| Pods in **all** namespaces | **ClusterRole** + ClusterRoleBinding |
| One ClusterRole, granted **per-namespace** | **ClusterRole** + **RoleBinding** (in each ns) |

> The demo for this comes in the next lecture, but the rule is exam-relevant: **Roles are namespace-bound; ClusterRoles are reusable and scope is decided by the *binding*.**

### Namespaced vs cluster-scoped resources

From `kubectl api-resources`, the `NAMESPACED` column:

| `NAMESPACED` | Meaning | Examples |
|---|---|---|
| **`true`** | Belongs to **one namespace** | `pods`, `deployments`, `services`, **`pvc`**, `configmaps`, `roles` |
| **`false`** | **Cluster-wide** | **`nodes`**, **`pv`** (persistent volumes), `clusterroles`, `storageclasses`, `csr` |

> Note the pairing: **PV is cluster-scoped; PVC is namespaced** (Day 27). `nodes` are cluster-wide — which is exactly why they have no namespace in their API path.

### The RBAC YAML (the file the lecture walks through)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader-role
  namespace: default          # omit → defaults to the current context's namespace
rules:
  - apiGroups: [""]           # "" = CORE group (pods live in v1)
    resources: ["pods"]
    verbs: ["get", "watch", "list"]
```

| Field | Explanation |
|---|---|
| **`rules`** is **plural** → you can have many rules in one Role | |
| **`apiGroups: [""]`** | **Empty = core.** For deployments you'd write `["apps"]` — because deployments live in `apps/v1` |
| **`resources: ["pods"]`** | The object type |
| **`verbs`** | The actions — `get`, `watch`, `list` here |

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pod-reader-binding
  namespace: default
subjects:
  - kind: User
    name: seema
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: pod-reader-role
  apiGroup: rbac.authorization.k8s.io
```

### The `apiGroup` nuance in `subjects` — a real exam trap

| Subject kind | `apiGroup` value |
|---|---|
| **`User`** | **`rbac.authorization.k8s.io`** |
| **`Group`** | **`rbac.authorization.k8s.io`** |
| **`ServiceAccount`** | **`""` (empty)** — because ServiceAccounts live in the **core** group |

> The lecture calls this out explicitly: *"if this were a service account, then the API group would have been blank because service accounts are part of the core group."* Getting this wrong is a silent failure — the binding applies but matches nobody.

---

### ABAC — Attribute-Based Access Control

> **Access granted based on attributes: user, verb, resource type, namespace.**

Sounds like RBAC — and it is, conceptually. The difference is **how it's expressed**:

| | **RBAC** | **ABAC** |
|---|---|---|
| Defined in | **Kubernetes objects** (Role/RoleBinding) | **A static JSON file** |
| Change requires | `kubectl apply` | **Restarting the API server** |
| Dynamic? | ✅ | ❌ |
| Introspection | `kubectl get role` | Read the file |
| Status | **Standard** | **Deprecated** |

```json
{"apiVersion": "abac.authorization.kubernetes.io/v1beta1", "kind": "Policy",
 "spec": {"user": "seema", "namespace": "default",
          "resource": "pods", "readonly": true}}
```

> ⚠️ **Do not confuse `abac.authorization.kubernetes.io` with a named API group.** It appears **only as a version marker for the config file** — there's no such resource group in a cluster.

**Why it's dead:** a static file that needs an **API server restart** for every permission change is untenable at scale — and `restarting the API server` means a control-plane blip.

---

### Webhook — Outsourced Authorization

> **The API server does not decide. It asks an external service.**

```
API server ──(SubjectAccessReview / decision request)──► Webhook service
                                                             │
                        allow / deny / no opinion ◄──────────┘
```

| Implementation | Notes |
|---|---|
| **OPA** (Open Policy Agent) | **CNCF** project — general policy engine |
| **Gatekeeper** | **OPA's Kubernetes extension**, adds **CRDs** for policies |

**Configuration:** a **webhook config file** — and unlike ABAC's JSON, it is **dynamic** (no API server restart for policy changes).

### What webhook gives you that RBAC cannot

> RBAC's entire universe is **(user, verb, resource, namespace)**. It cannot express **conditions**.

Real policies that **require** webhook:

| Policy | Why RBAC can't |
|---|---|
| **Only the security team may delete pods in production** | Not a role/verb/resource question — it's a *team* attribute combined with an action |
| **Developers may scale deployments to at most 25 replicas** | RBAC sees `patch deployments`, not **field values** |
| **CI/CD may only deploy images signed by our internal registry** | Depends on **image content**, invisible to RBAC |

> **RBAC = who/what/where. Webhook = under what conditions.**
>
> This is the single best sentence in the lecture for interview answers.

**Where you'll meet it:** **large, security-conscious environments** — banking, healthcare. Also note *"it offloads your RBAC in some way"* — a webhook can handle everything alone, but production uses the combination.

---

### Node Authorizer — the one that's always on

> **Enabled by default. No configuration, no Roles, no bindings.** The logic is **built into the API server**.

**The problem it solves:** kubelet runs on every node. How do you ensure the kubelet on **worker-1** can only see **worker-1's** pods — not the whole cluster's?

```
Node authorizer:
  the kubelet for node X  →  may only read/write data about  →  node X's own pods & secrets
```

That's exactly what a node needs to do its job: *fetch pod specs, hand them to the container runtime, report status.*

Related to Day 33's finding — the API server doesn't verify kubelet's **serving** certificate but relies on **RBAC node authorization + NodeRestriction**. This is that mechanism.

> **Always enabled in practical clusters**, because without it kubelets couldn't function.

---

### AlwaysAllow / AlwaysDeny

| Mode | Behaviour | When |
|---|---|---|
| **`AlwaysAllow`** | Any **authenticated** request is permitted — **no restrictions at all** | Testing, throwaway clusters, demos. **Never production** |
| **`AlwaysDeny`** | **Every** request is denied | **Complete lockdown** — e.g. a live security incident where you want nobody acting on the cluster |

**Why `AlwaysAllow` is dangerous:** whoever authenticates can do **anything**, including deleting every namespace. Even the instructor has **never** seen it used.

**The interesting question about `AlwaysDeny`:** if everyone is denied, **how do you turn it back off?** (The instructor leaves this as a puzzle for the comments.)

> Real answer, for your notes: you edit the static pod manifest on the control-plane **node** — filesystem access, not API access. Because the API server is a static pod, changing `/etc/kubernetes/manifests/kube-apiserver.yaml` and letting the kubelet restart it restores the config. **The API is locked; the filesystem isn't.**

---

## 10) How Multiple Modes Combine — the Evaluation Rule

> **Modes are evaluated in the order listed. Each returns one of three verdicts.**

| Verdict | Effect |
|---|---|
| **Allow** | **Request proceeds. Evaluation STOPS.** |
| **Deny** | **Request rejected. Evaluation STOPS.** |
| **NoOpinion** | **Passes to the next mode** |

> **This is the most important mechanic in the lecture.** An `Allow` from an early mode means later modes are **never consulted** — which has a surprising consequence: a permissive early mode can **bypass** a restrictive later one.

### Walkthrough — Seema logs in

```
kubectl get pods (as Seema)
        │
        ▼
   [authentication]  ✅
        │
        ▼
   [Node authorizer]  → NoOpinion   (Node only serves kubelets)
        │
        ▼
   [RBAC]             → Allow / Deny   → final
```

That's why on a `--authorization-mode=Node,RBAC` cluster, human permissions are **entirely** RBAC's job.

---

## 11) Where Authorization Is Configured

**Authorization happens in the API server** — so its config lives in the API server's **static pod manifest**:

```bash
docker ps                                   # find the control-plane container (kind)
docker exec -it <control-plane> bash
cd /etc/kubernetes/manifests
cat kube-apiserver.yaml
```

```yaml
    - --authorization-mode=Node,RBAC
```

| Observation | Meaning |
|---|---|
| **`Node,RBAC`** | Two modes, **evaluated in that order** |
| **`Node`** | Always present |
| **`RBAC`** | This cluster's real authorization |

### Changing the modes

| Task | What to do |
|---|---|
| **Add webhook** | Append: `--authorization-mode=Node,RBAC,Webhook` |
| **Enable ABAC** | `--authorization-mode=Node,ABAC` **plus** `--authorization-policy-file=<json>` |
| **Enable webhook** | **plus** `--authorization-webhook-config-file=<path>` |
| **AlwaysAllow / AlwaysDeny** | **Replace the whole list**: `--authorization-mode=AlwaysAllow` |

> The static pod manifest lives on the **node's filesystem**, so the **kubelet notices the change and restarts the pod automatically** — no API call needed. (This is how you'd escape `AlwaysDeny`.)

### Managed clusters — you may not see any of this

> With **GKE, AKS, EKS**, the **control plane is hidden**. There is **no guarantee** it's even static pods — it could be VMs or containers. All you know is it's **highly available**.

So on managed services, *"check the API server manifest"* is often **not available to you**. Know the theory anyway — the exam and most self-managed clusters do expose it.

### Version note

Newer Kubernetes (1.29+) also supports an **`AuthorizationConfiguration`** file as an alternative to the `--authorization-mode` string. Both may appear in the wild; `--authorization-mode=Node,RBAC` remains the common form.

---

## 12) The Two Scenarios — RBAC vs Webhook vs Both

**The requirements:**

1. **Permission:** Seema may **create pods**.
2. **Policy:** she may create pods **only if the image comes from `registry.pinkco.company.com`**.

### Option 1 — Webhook only

```
Seema: kubectl apply -f pod.yaml
   │
   ▼
[authentication] ✅
   │
   ▼
[Node] → NoOpinion
   │
   ▼
[Webhook / OPA] → decides BOTH
        ├── does Seema have permission to create pods?  ✅
        └── is the image from registry.pinkco.company.com?  ✅
   │
   ▼
ALLOW
```

**Both permission and policy handled by the OPA agent.** The API server's `--authorization-mode` would be `Node,Webhook` (or webhook alone plus Node).

> **This works** — but *"in production implementations, you will not see just webhook being used alone."* It's an interesting mental model, not a recommendation.

### Option 2 — Webhook + RBAC (the production pattern)

```
Seema: kubectl apply -f pod.yaml
   │
   ▼
[authentication] ✅
   │
   ▼
[Node] → NoOpinion          (Node only serves kubelets)
   │
   ▼
[Webhook / OPA]  → checks ONLY the image registry
        ├── image NOT from allowed registry → **DENY** → stops here ❌
        └── image OK                        → **NoOpinion** ← deliberately!
   │
   ▼
[RBAC]  → checks ONLY permissions
        ├── Seema may create pods → **Allow** ✅
        └── otherwise            → **Deny** ❌
```

**The subtle, brilliant part:** the webhook returns **`NoOpinion`** — **not `Allow`** — when the image is fine.

> Why? Because **if OPA returned `Allow`, evaluation would stop** and RBAC would **never run**. A user with **no permission** would still get through, having merely satisfied the image policy. **Returning `NoOpinion` delegates the permission check to RBAC.**

| Scenario | Verdict chain | Result |
|---|---|---|
| Image from wrong registry | `NoOpinion → Deny` | ❌ denied at webhook |
| Image fine, user has RBAC | `NoOpinion → NoOpinion → Allow` | ✅ allowed |
| Image fine, user lacks RBAC | `NoOpinion → NoOpinion → Deny` | ❌ denied at RBAC |

> **The design principle:** each mode answers **one question**, and `NoOpinion` is how you say *"not my department — ask the next one."* Webhook handles **conditions**; RBAC handles **permissions**. That separation is what makes the combination maintainable.

---

## 13) Key Takeaways

1. **The Kubernetes API ≠ the API server.** The API server is a **physical component** with many duties; the **API** is a **logical** interface **hosted inside** it.
2. **The Kubernetes API is RESTful** — HTTP verbs on resources. **`kubectl` translates** human commands into REST calls.
3. **Public endpoints:** `/version`, `/healthz`, `/livez`, `/readyz` — the **Z** avoids collisions with future resources named `health`/`ready`.
4. **Resource endpoints:** **`/api`** (core) and **`/apis`** (named groups).
5. **`/metrics`** is Prometheus-format but **requires authentication** (else `403`).
6. **`/logs`** returns **API server** logs (with flags), is **not official**, and is **not** what `kubectl logs` uses (that's the **kubelet**).
7. **`curl` needs `-k`** against the API server because your host lacks the cluster CA — never in production.
8. **`kubectl proxy`** runs a **localhost HTTP proxy** that authenticates with **your kubeconfig** and speaks **HTTPS** upstream.
9. **`kubectl proxy` ≠ `kube-proxy`.** One is a CLI proxy; the other a per-node DaemonSet doing Service networking.
10. **Core group `/api/v1` has no group name in the path** for **backwards compatibility**; **named groups `/apis/<group>/<version>`** carry everything newer.
11. **`apiVersion` in YAML = `<group>/<version>`**, or just `<version>` for core — hence **`apiGroups: [""]`** means core in RBAC.
12. **API path:** `/{root}/{group?}/{version}/namespaces/{ns}/{resource}/{name}`; **cluster-scoped resources omit the namespace segment**.
13. **Authentication = who; authorization = what.** Three identity types: **users, groups, service accounts**.
14. **RBAC** = who/what/on which resources, via **Role / RoleBinding / ClusterRole / ClusterRoleBinding**; **99% of clusters**.
15. **A ClusterRole CAN hold namespaced resources.** The **binding** decides scope: ClusterRoleBinding → all namespaces; RoleBinding → one namespace.
16. **PV, nodes, clusterroles, storageclasses, CSRs are cluster-scoped**; **pods, PVCs, deployments are namespaced**.
17. **ABAC is deprecated**, uses a **static JSON file**, and needs an **API server restart** per change. Its `apiGroup` string is **config-file only**, not a real API group.
18. **Webhook outsources authorization** to **OPA/Gatekeeper**; config is dynamic; it's how you express **conditional** policy that RBAC cannot.
19. **Node authorizer is always on and needs no configuration** — it's what limits a kubelet to its own node's data.
20. **`AlwaysAllow` is never production; `AlwaysDeny` is for lockdown** — and you escape it via the **static pod manifest on the node**, not the API.
21. **Modes evaluate in order; `Allow`/`Deny` stop evaluation, only `NoOpinion` continues.** This is the mechanic that makes combinations work.
22. **In the production pattern, the webhook returns `NoOpinion` on success** so RBAC still gets to decide permissions — otherwise a permissive webhook would bypass RBAC entirely.
23. **Config lives in `--authorization-mode`** in `/etc/kubernetes/manifests/kube-apiserver.yaml`; **managed clusters hide it.**

---

## 14) Essential Commands

```bash
# --- API discovery ---
kubectl config view                        # find the API server address
kubectl api-resources                      # groups, versions, namespaced?, shortnames
kubectl api-versions                       # available apiVersions
kubectl explain pod                        # schema for a resource

# --- Direct REST calls (lab only) ---
curl -k https://<server>:<port>/version
curl -k https://<server>:<port>/livez
curl -k https://<server>:<port>/readyz
curl -k https://<server>:<port>/healthz
curl -k https://<server>:<port>/metrics          # 403 — needs auth

# --- Via the local proxy (authenticated by your kubeconfig) ---
kubectl proxy                                     # 127.0.0.1:8001
curl http://127.0.0.1:8001/version
curl http://127.0.0.1:8001/metrics
curl http://127.0.0.1:8001/api/v1/namespaces/default/pods
curl http://127.0.0.1:8001/apis/apps/v1/namespaces/default/deployments
curl http://127.0.0.1:8001/apis/rbac.authorization.k8s.io/v1/clusterroles

# --- Where authorization is configured ---
docker ps
docker exec -it <control-plane-container> bash
cd /etc/kubernetes/manifests && cat kube-apiserver.yaml | Select-String authorization-mode

# --- Check effective permissions ---
kubectl auth can-i create pods
kubectl auth can-i list pods --as seema
kubectl auth whoami
```

### The RBAC pair (from the lecture)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: default
rules:
  - apiGroups: [""]            # "" = core group
    resources: ["pods"]
    verbs: ["get", "watch", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pod-reader-binding
  namespace: default
subjects:
  - kind: User
    name: seema
    apiGroup: rbac.authorization.k8s.io      # "" if kind: ServiceAccount
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

---

## 15) Quick Self-Check

1. What's the difference between the Kubernetes API and the API server?
2. Name four responsibilities of the API server besides hosting the API.
3. Who converts `kubectl get pods` into a REST call, and what does that call look like?
4. Why do `/healthz`, `/livez`, `/readyz` end in **z**?
5. Which endpoints need no authentication, and why is that safe?
6. Does `/logs` give you pod logs? What does `kubectl logs` actually call?
7. Why does `curl` need `-k` here, and what's the risk?
8. What does `kubectl proxy` do, and how does it authenticate?
9. Give three differences between `kubectl proxy` and `kube-proxy`.
10. Why does the core group have no name in its path?
11. Which `apiVersion` would you write for a Job, a Deployment, and a ClusterRole?
12. What does `apiGroups: [""]` mean in a Role?
13. Write the API path for pods in `app1`, and for clusterroles. What's structurally different?
14. Is `pv` namespaced? Is `pvc`?
15. Can a ClusterRole contain `deployments`? What determines whether the user gets access in one namespace or all?
16. What does ABAC require that RBAC doesn't — and why is that fatal at scale?
17. Name two policies RBAC **cannot** express and webhook can.
18. What exactly does the Node authorizer guarantee, and who configures it?
19. If a mode returns **Allow**, do later modes get consulted? What about **NoOpinion**?
20. In the RBAC + Webhook scenario, why must the webhook return **NoOpinion** rather than **Allow**?
21. Where do you change `--authorization-mode`, and how does that change take effect without an API call?
22. You've enabled `AlwaysDeny` and locked yourself out. How do you recover?

---

## What's Next (Day 36)

- **RBAC deep dive** — roles, bindings, verbs, aggregation, service accounts, and the full authorization flow in practice.

---

*End of Day 35 notes.*
