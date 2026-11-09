# Admission Controllers — Mutating, Validating & Webhooks (Day 38)

> Source: Day 38 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: What happens **between authorization and etcd** — **admission control**: built-in **mutating** and **validating** plugins, the **enable/disable** flags, **admission webhooks** vs **authorization webhooks**, and the **execution order**.
> Prerequisite: Day 19 (LimitRange, requests/limits), Day 22 (`imagePullPolicy`, termination), Day 26 (storage classes), Day 35 (authorization modes, `NoOpinion`), Day 36 (RBAC), Day 37 (ServiceAccounts).
> Next: **Custom Resource Definitions (CRDs)** — Day 39.

---

## 1) Where Admission Control Sits

The lecture opens with the request flow everyone thinks they know:

```
Seema: kubectl apply -f pod.yaml
   │
   ▼
[authentication]  ← certificates, external IdP, or bearer tokens (Day 37)
   │
   ▼
[authorization]   ← RBAC, or a webhook authorizer like OPA (Day 35/36)
   │
   ▼
[  ADMISSION  ]   ← ⬅ THE MISSING PIECE
   │
   ▼
  etcd
```

> **Admission control sits between authorization and etcd**, and it is **configured in the API server** — exactly like authentication and authorization.

### And it's still the API server that decides

Even when you outsource:
- **authentication** to an external IdP → the **API server** validates the token (Day 37)
- **authorization** to OPA → the **API server** asks OPA but makes the final call

> *"The final approval comes from the API server."* Admission control follows the same pattern: **the API server** runs the plugins, whether built-in or webhook-backed.

---

## 2) Why Authentication + Authorization Is Not Enough

The reasonable objection: *"If my request is authenticated and authorized, isn't that enough?"*

**No — because authn/authz answer *who* and *what*, not *under which conditions*.**

### Policies you cannot express with authn/authz

| Requirement | Why RBAC fails |
|---|---|
| **Public images are prohibited** | RBAC sees `create pods`, not the **image name** inside the pod spec |
| **A sidecar must be injected into every pod** | RBAC cannot **add** anything |
| **Every pod must carry default labels** | RBAC cannot **modify** an object |
| **A namespace has a memory/vCPU budget** | RBAC has no notion of consumption |

> Day 35 said it best: **RBAC = who/what/where. The conditions need something else.** That "something else" is admission control — the in-cluster equivalent of the webhook authorizer's job, but with **visibility into the full request body**.

### So admission control does two things

| Job | Meaning |
|---|---|
| **Mutate** | **Modify** the request (add a sidecar, add labels, set a default StorageClass), then forward it to etcd |
| **Validate** | **Allow or deny** based on the request's parameters |

> Both jobs happen **before** the object is stored. Nothing reaches etcd unexamined.

---

## 3) Mutating vs Validating

| | **Mutating** | **Validating** |
|---|---|---|
| Action | **Modifies** the request | **Allows or denies** it |
| Can it deny? | ❌ **Never** | ✅ **Yes** |
| Order | **First** | **Second** |
| The instructor's analogy | **X-Men mutants** — modified DNA, special powers | A **bouncer** with a checklist |

> The X-Men framing is the memorable one: *mutants* have **modified DNA**, so **mutating** controllers **modify** your request.

**Critical ordering fact, repeated throughout the lecture:**

> **Mutating admission controllers are applied first. Validating admission controllers are applied after.**

### And the asymmetry that matters for exams

> **Mutating controllers cannot deny. Only validating controllers can allow or deny.**

A mutating controller that dislikes your request can only **rewrite** it — never reject it.

---

## 4) Built-In Mutating Plugins

### 4.1 `DefaultStorageClass`

Day 26/27: a PVC may omit `storageClassName`. Something has to fill it in.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"     # ← marks the default
provisioner: ebs.csi.aws.com
```

> If a PVC **omits** the storage class, the **mutating** `DefaultStorageClass` plugin **injects** the default class's name. That's why a PVC with no class still gets a `gp3` volume.

**If no class is marked default** and the PVC omits it → the PVC stays **unbound** (that's your clue to check the annotation).

### 4.2 `DefaultTolerationSeconds`

Day 22: a **`NoExecute`** taint evicts running pods immediately — but abrupt shutdown is bad for applications.

> The plugin **adds a default toleration of 5 minutes** so pods get time to **terminate gracefully** before eviction completes. If the pod still hasn't gone, it's force-terminated.

**This is why a `NoExecute` taint doesn't instantly kill your pods** — most people never realise a mutating plugin is the reason.

### 4.3 `DefaultIngressClass`

The ingress analogue of StorageClass. A cluster can run **several ingress controllers** (on EKS: **HAProxy**, **AWS ALB**, **nginx**). If an Ingress object **doesn't name a controller**, one must be chosen.

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
  annotations:
    ingressclass.kubernetes.io/is-default-class: "true"
```

> The plugin **associates the Ingress with the default ingress class** — provided you marked one as default.

> Ingress itself comes later in the course; this is awareness-level for now.

---

## 5) Built-In Validating Plugins

### 5.1 `NodeRestriction`

Day 33: the API server doesn't verify the kubelet's serving cert; it relies on **RBAC node authorization + `NodeRestriction`**.

> **`NodeRestriction` ensures a kubelet can only modify its own Node object and the pods running on it** — nothing else.

*"But why would the kubelet on worker-1 touch worker-2?"* — it wouldn't, **unless it's compromised.**

> **The threat model:** if worker-1 is hacked, the attacker inherits its kubelet credentials. Without this plugin, a compromised node could **manipulate other nodes' pods** — a lateral-movement bridge. `NodeRestriction` closes it.

### 5.2 `ResourceQuota`

> A namespace with a quota — e.g. **50 GB memory, 24 vCPU** — cannot exceed it.

If `prod` is already consuming its entire quota and a new pod requests more, **the request is denied at admission time**.

**This is a validate-time decision:** the plugin compares the incoming request against **current consumption + quota**.

> ResourceQuota is the enforceable version of Day 19's "fair resource distribution" — it operates on the **namespace**, not the node.

### 5.3 `NamespaceLifecycle`

Day 29's demo error — `namespaces "logging-ns" not found` — came from **this plugin**.

Two jobs:

| Job | Effect |
|---|---|
| **Reject resources in non-existent namespaces** | You cannot create a pod in a namespace that isn't there |
| **Reject resources in a *terminating* namespace** | During `delete ns`, nothing new can be created inside it |

> The second one explains why a namespace seems to "hang" in `Terminating` — **nobody can add anything to finish the cleanup**, and the finalizers must drain on their own.

---

## 6) Dual-Function Plugins (Mutate *and* Validate)

Most plugins are one or the other. **Three important ones do both** — and the order rule means their **mutating half runs first, validating half later**.

### 6.1 `LimitRanger`

Day 19's LimitRange object:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: defaults
  namespace: default
spec:
  limits:
    - type: Container
      default:           { cpu: 500m, memory: 512Mi }   # injected if absent
      defaultRequest:    { cpu: 250m, memory: 256Mi }   # injected if absent
      max:               { cpu: "4",  memory: 8Gi }     # rejected if exceeded
      min:               { cpu: 100m, memory: 128Mi }
```

| Half | What it does |
|---|---|
| **Mutating** | Adds `default`/`defaultRequest` to containers that specify nothing |
| **Validating** | **Rejects** any pod requesting more than `max` (4 vCPU / 8 GiB here) or less than `min` |

> That's exactly the behaviour you saw in the Day 19 demo — pod specs "magically" gained requests and limits.
>
> **One object, two admission phases.**

### 6.2 `AlwaysPullImages`

**The mutating half:**

> Whatever `imagePullPolicy` you set — `IfNotPresent`, `Never` — the plugin **resets it to `Always`**.

**The validating half — and the security argument:**

Day 22: `IfNotPresent` uses the **node's cache**. If an image is already cached, **no registry credentials are consulted**.

> **The attack:** a container **without** access to a private registry can still run a cached private image — because nothing re-checks credentials.

`AlwaysPullImages` forces a pull on every start, so:
1. **The image is always pulled** from the registry.
2. **Credentials are checked every time**, so containers **without** access to that private registry **cannot** use the image — cached or not.

> **Technical accuracy note:** the plugin doesn't perform a separate "credential validation" step; it works by **forcing the pull**, which makes the kubelet's normal image-pull-secret check unavoidable. The lecture's framing ("it validates credentials") describes that outcome.

### 6.3 `ServiceAccount`

| Half | Behaviour |
|---|---|
| **Mutating** | If a pod specifies no `serviceAccountName`, **default** it to `default` — and mount the projected token (Day 37) |
| **Validating** | If the referenced ServiceAccount **doesn't exist**, the request is **rejected** |

> This plugin is why **every pod has a `default` SA mounted** without you asking — and why **deleting the `default` SA breaks pod creation** in that namespace.

---

## 7) Enabled by Default vs Opt-In

> **Most of these plugins are enabled by default — in the API server's *code*, not in its flag.**

```bash
docker ps
docker exec -it <control-plane-container> bash
cd /etc/kubernetes/manifests
cat kube-apiserver.yaml | Select-String admission
```

You'll typically see **only one** listed:

```yaml
- --enable-admission-plugins=NodeRestriction
```

*"But you said most are enabled by default — I only see NodeRestriction?"*

> Because the rest are **compiled-in defaults**. The **flag shows only additions**, not the full set. Check the official **admission controllers reference** for the complete default list.

| Plugin | Default? |
|---|---|
| `NamespaceLifecycle`, `LimitRanger`, `ServiceAccount`, `DefaultStorageClass`, `DefaultTolerationSeconds`, `NodeRestriction`, `ResourceQuota`, `MutatingAdmissionWebhook`, `ValidatingAdmissionWebhook`, `DefaultIngressClass` | ✅ **enabled** |
| **`AlwaysPullImages`** | ❌ **disabled** |

> **That resolves the objection about `AlwaysPullImages`:** *"In production I always see `IfNotPresent` respected."* Correct — because the plugin that would override it **isn't on by default**. Enable it and `IfNotPresent` gets rewritten to `Always`.

### The flags

| Flag | Purpose |
|---|---|
| **`--enable-admission-plugins`** | Add plugins (comma-separated) |
| **`--disable-admission-plugins`** | Remove plugins (including code-level defaults) |

Both live in the **API server static pod manifest** — and editing it **restarts the API server automatically** (Day 35).

> If your control plane runs as a **systemd service** instead, these flags are in the **unit file**, not a pod manifest.

---

## 8) Demo — Disabling the `ServiceAccount` Plugin

### Baseline

```bash
kubectl run my-pod --image=nginx
kubectl describe pod my-pod
```

Look for:

```
Service Account:  default
...
Mounts:
  /var/run/secrets/kubernetes.io/serviceaccount from kube-api-access-xxxxx (ro)
```

> The mount and the `Service Account: default` line are **both the mutating plugin's work**. (`describe` doesn't show the SA's *contents* — that's the three files from Day 37.)

### Disable it

```bash
# inside the control-plane node
vim /etc/kubernetes/manifests/kube-apiserver.yaml
```

```yaml
    - --disable-admission-plugins=ServiceAccount
```

> Save → **the kubelet restarts the API server pod** (visible as it flickers `Pending` → `Running` with `kubectl get pods -n kube-system -w`).

### The result

```bash
kubectl run my-pod-2 --image=nginx
kubectl describe pod my-pod-2
```

```
Service Account:  <none>          ← or absent entirely
Mounts:           <none>          ← no projected token
```

> **No ServiceAccount, no token, no `ca.crt`.** That pod **cannot authenticate to the API server at all** — it has no credentials.

> This is also the mechanism behind the **`automountServiceAccountToken: false`** effect (Day 37) — different switch, same outcome on the pod spec.

### Revert

```bash
vim /etc/kubernetes/manifests/kube-apiserver.yaml
# remove the --disable-admission-plugins line
```

> Save → API server restarts again → behaviour returns to normal.

**Lesson:** default-enabled plugins aren't visible in the flag, but they **are** disable-able — and the effect is immediate and visible in every new pod.

---

## 9) Admission Webhooks — the Bridge to Custom Controllers

### Two levels

```
Admission controllers
├── BUILT-IN
│   ├── mutating        (DefaultStorageClass, DefaultTolerationSeconds, …)
│   ├── validating      (NodeRestriction, ResourceQuota, NamespaceLifecycle, …)
│   └── dual            (LimitRanger, AlwaysPullImages, ServiceAccount)
└── CUSTOM
    ├── via external policy engines  (OPA/Gatekeeper, Kyverno)
    └── organisation-specific         (your own implementation)
```

**Custom controllers don't come with Kubernetes.** Two ways to get one:

| Route | Examples |
|---|---|
| **Use an existing policy engine** | **OPA + Gatekeeper**, **Kyverno** |
| **Write your own** | Organisation-specific logic |

### The two bridge plugins

> **`MutatingAdmissionWebhook`** and **`ValidatingAdmissionWebhook`** are **built-in** plugins whose only job is to **call your custom controller**.

They are the **bridge** — the API server's way of reaching a webhook server you deployed.

```
API server  ──(HTTP callback)──►  custom controller (OPA/Gatekeeper/Kyverno)
            ◄── allow / deny / patch ──
```

> Custom admission controllers **typically run as Deployments inside your cluster**. Very rarely they run outside.

### What a webhook *is*

> **A webhook is an HTTP callback: one system notifies or requests another system in real time when an event occurs.**

**The plain-English example:** commit to a GitHub repo → your Jenkins pipeline runs. **How?** A webhook fires on the commit and tells Jenkins to start the build.

**In Kubernetes:** the API server calls an external service during admission:

> *"Hey external service, before I accept this request — do you want to **approve**, **reject**, or **modify** it?"*
>
> modify → **mutation** · allow/deny → **validation**

### The webhook configuration object

A `MutatingWebhookConfiguration` / `ValidatingWebhookConfiguration` names the service, the CA bundle, and which requests to intercept:

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: policy-validator
webhooks:
  - name: validate.example.com
    admissionReviewVersions: ["v1"]
    sideEffects: None
    failurePolicy: Fail                    # Fail closed | Ignore
    timeoutSeconds: 10
    rules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["pods"]
    clientConfig:
      service:
        name: policy-webhook
        namespace: policy
        path: /validate
      caBundle: <base64 CA>
```

> `failurePolicy: Fail` means **"if the webhook is unreachable, reject the request"** — the safe default for security policy, at the cost of availability. `Ignore` does the opposite.

---

## 10) Webhook *Authorization* vs Webhook *Admission* — the Correction

This is where the lecture fixes an **oversight from Day 35**.

### What a webhook *authorizer* can see

> **A webhook authorizer sees only: user, group, service account, verb, resource, namespace.**

That is **exactly what RBAC sees**. **It never sees the request body** — so it **cannot** inspect the pod's `image` field.

### Therefore the Day 35 claim was too strong

Day 35 said the requirement *"only allow images from `registry.pinkco.company.com`"* could be met by **webhook authorization alone, or webhook + RBAC**.

> **Correction: a webhook *authorizer* cannot evaluate the image.** That check needs **admission control**, which **sees the full object**.

**The corrected flow:**

```
Seema: kubectl apply -f pod.yaml
   │
   ▼
[authentication] ✅
   │
   ▼
[AUTHORIZATION: --authorization-mode=Node,Webhook,RBAC]
   ├── Node   → NoOpinion
   ├── Webhook(OPA) → NoOpinion          ← can only check attributes, NOT the image
   └── RBAC   → Allow (Seema may create pods)
   │
   ▼
[ADMISSION: OPA Gatekeeper as a validating webhook]
   └── "Is the image from registry.pinkco.company.com?"  → Allow / Deny
   │
   ▼
  etcd
```

> **The two OPA roles answer different questions:** the authorizer checks **who/what/where** (plus time/network attributes); the admission controller checks **what's actually inside the object** — like the image.

### What an OPA webhook *authorizer* is uniquely good for

Since it sees the same fields as RBAC, why use it at all? **Three things RBAC cannot do:**

| Capability | Example |
|---|---|
| **Time-based access** | *"Only authorize changes after 6 p.m. — never during production hours"* |
| **Network-aware checks** | *"Only allow requests originating from these CIDRs/subnets"* |
| **Early rejection** | The request dies **before** admission — cheaper and faster |
| **Centralized access decisions** | One policy server for **hundreds of clusters** instead of RBAC copied everywhere |

> That last one is the real enterprise argument: **RBAC is per-cluster**. With 200 clusters you don't want 200 copies of a policy. A central OPA server gives **one decision point**.

And the ordering rule (Day 35) preserves the division of labour:

> **OPA returns `NoOpinion` when its checks pass** — so the request proceeds to RBAC, which decides actual permissions. If OPA `Allow`ed, RBAC would never run and permissions would be bypassed.

---

## 11) What Production Actually Looks Like

```
--authorization-mode=Node,RBAC          ← the defaults
admission: OPA Gatekeeper               ← the policy layer
```

> **No webhook authorizer in the common case.** Most production clusters run **Node + RBAC** for authorization and put **all the conditional policy into admission control**, where the full object is visible.

### Typical admission policies

| Policy | Type needed |
|---|---|
| Only allow images from approved registries | **Validating** |
| Containers must not run as root | **Validating** |
| All pods must have `team` and `env` labels | **Validating** |
| Inject default labels if missing | **Mutating** |

> Note the pairing: **"must have" = validating** (rejects), **"inject if missing" = mutating** (fixes it for you). Choosing the wrong type is a common design error — one you can now avoid.

---

## 12) The Execution Order

### The two guarantees

1. **All mutating controllers run first**, then **all validating controllers**.
2. Mutations are held **in memory** — nothing is persisted to etcd until **every** validating controller has approved.

```
request
  │
  ├─► [mutating #1] ─► [mutating #2] ─► [mutating #3] ─► …   (modified object, in MEMORY)
  │                                                        │
  │                                                        ▼
  └─────────────────────────────────────────────► [validating #1] ─► [validating #2] ─► …
                                                           │
                                            all pass ──────┴──────► etcd
                                            any denies ────────────► error to client
```

### And the scope limit

> **Admission control only applies to WRITE operations** — `create`, `update`, `patch`, `delete`.

**`get`, `list`, `watch` do not go through admission.**

> Think of it **from etcd's perspective**: if the request would **write**, **modify**, or **patch** something in etcd, it goes through admission. If it only **reads**, it doesn't.

That's why `kubectl get pods` is cheap and never rejected by a policy — and why a bad policy can't break reads, only writes.

### Worked example — one pod through the whole chain

Enabled plugins: `NamespaceLifecycle, LimitRanger, ServiceAccount, MutatingAdmissionWebhook, ValidatingAdmissionWebhook, ResourceQuota`.

**Phase 1 — mutating only:**

| Plugin | Action |
|---|---|
| `NamespaceLifecycle` | **skipped** — validating |
| `LimitRanger` | **mutating half**: no requests/limits specified → **injects defaults** |
| `ServiceAccount` | **mutating half**: `serviceAccountName` absent → **sets `default`, mounts token** |
| `MutatingAdmissionWebhook` | calls custom controller → e.g. **injects a logging sidecar** (or a service-mesh proxy) |
| `ValidatingAdmissionWebhook` | **skipped** — validating |
| `ResourceQuota` | **skipped** — validating |

> *"Whatever changes they did, all of that was stored **in memory**. Nothing was persisted in etcd."*

**Phase 2 — validating only:**

| Plugin | Action |
|---|---|
| `NamespaceLifecycle` | namespace **exists** → ok |
| `LimitRanger` | **validating half**: is the pod within `max`? → ok |
| `ServiceAccount` | **validating half**: does the SA exist? → ok |
| `ValidatingAdmissionWebhook` | e.g. image from a **private registry** allowed? → ok |
| `ResourceQuota` | does the **namespace have quota left**? → ok |

**All approve → the object is written to etcd.**

> **If any validating controller denies, the whole request fails** — and all the mutations evaporate, because they were never committed.

---

## 13) Key Takeaways

1. **Admission control sits between authorization and etcd**, configured in the API server.
2. **The API server makes the final call** — even when authentication/authorization are outsourced.
3. **Authn + authz cannot express policy.** Image registries, injected sidecars, default labels, namespace budgets — all need admission.
4. **Mutating controllers modify; validating controllers allow/deny.**
5. **Mutating controllers can NEVER deny.** Only validating controllers do.
6. **All mutating controllers run first, then all validating.**
7. **Mutations live in memory** until every validating controller approves — nothing hits etcd early.
8. **Admission applies only to write operations** (`create`/`update`/`patch`/`delete`), never `get`/`list`/`watch`.
9. **Built-in mutating:** `DefaultStorageClass`, `DefaultTolerationSeconds` (5 min), `DefaultIngressClass`.
10. **Built-in validating:** `NodeRestriction` (kubelet confined to its node), `ResourceQuota`, `NamespaceLifecycle` (missing **and terminating** namespaces).
11. **Dual-function:** `LimitRanger` (injects defaults **and** enforces min/max), `AlwaysPullImages` (**forces `Always`**, so private-registry credentials are rechecked), `ServiceAccount` (**defaults the SA** and **validates it exists**).
12. **Most plugins are enabled by default in the API server's code** — that's why the flag only shows `NodeRestriction`.
13. **`AlwaysPullImages` is disabled by default** — which is why `IfNotPresent` is respected in most clusters.
14. **`--enable-admission-plugins`** / **`--disable-admission-plugins`** in the API server manifest; **editing restarts the API server**.
15. **Disabling `ServiceAccount`** removes the default SA mount — the pod then has **no API credentials at all**.
16. **Custom admission controllers** come from policy engines (**OPA/Gatekeeper, Kyverno**) or your own code, typically a **Deployment**.
17. **`MutatingAdmissionWebhook` / `ValidatingAdmissionWebhook` are built-in bridges** that call custom controllers.
18. **A webhook is an HTTP callback** — the GitHub→Jenkins trigger is the same mechanism.
19. **A webhook *authorizer* sees only user/group/SA/verb/resource/namespace — NOT the request body.** So it **cannot** check the image.
20. **The Day 35 image-registry requirement needs ADMISSION**, not just webhook authorization. (Correction, stated in this lecture.)
21. **OPA as an authorizer** adds time-based and network-aware checks, early rejection, and **centralized decisions across many clusters**.
22. **OPA returns `NoOpinion`** when its checks pass, so RBAC still decides permissions.
23. **Production shape: `Node,RBAC` + OPA Gatekeeper at admission.**
24. **"Must have X" = validating; "inject X if missing" = mutating.**

---

## 14) Essential Commands

```bash
# --- Where admission is configured ---
docker ps
docker exec -it <control-plane-container> bash
cd /etc/kubernetes/manifests
cat kube-apiserver.yaml | Select-String "admission"

# --- The flags ---
#   --enable-admission-plugins=NodeRestriction
#   --disable-admission-plugins=ServiceAccount

# --- Watch the API server restart after an edit ---
kubectl get pods -n kube-system -w

# --- Observe plugin effects ---
kubectl run my-pod --image=nginx
kubectl describe pod my-pod        # Service Account: default  +  Mounts: ...

# after disabling the ServiceAccount plugin:
kubectl run my-pod-2 --image=nginx
kubectl describe pod my-pod-2      # no SA, no mounts

# --- Custom admission (policy engines) ---
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations
kubectl get clusterrole | Select-String gatekeeper      # Gatekeeper's own RBAC
kubectl get pods -n gatekeeper-system

# --- Related policy objects ---
kubectl get resourcequota -n prod
kubectl get limitrange -n default
kubectl get storageclass
kubectl get ingressclass
```

### A LimitRange (dual-function, in one object)

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: defaults
  namespace: default
spec:
  limits:
    - type: Container
      default:        { cpu: 500m, memory: 512Mi }
      defaultRequest: { cpu: 250m, memory: 256Mi }
      max:            { cpu: "4",  memory: 8Gi }
      min:            { cpu: 100m, memory: 128Mi }
```

### A webhook configuration

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: policy-validator
webhooks:
  - name: validate.example.com
    admissionReviewVersions: ["v1"]
    sideEffects: None
    failurePolicy: Fail
    timeoutSeconds: 10
    rules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["pods"]
    clientConfig:
      service: { name: policy-webhook, namespace: policy, path: /validate }
      caBundle: <base64 CA>
```

---

## 15) Quick Self-Check

1. Where exactly does admission control sit in the request flow?
2. Give three policies that authentication and authorization **cannot** enforce, and say why.
3. What are the two jobs of admission control?
4. Can a mutating admission controller deny a request? Can a validating one modify it?
5. Which runs first — mutating or validating? What happens to mutations if validation fails?
6. Which operations trigger admission control, and which don't? Why that boundary?
7. What annotation marks a default StorageClass? Which plugin consumes it?
8. What does `DefaultTolerationSeconds` do, and what default does it use?
9. What does `NodeRestriction` protect against — describe the threat, not just the rule.
10. Name the two jobs of `NamespaceLifecycle`. Why does the second matter during a namespace deletion?
11. `LimitRanger` is "dual-function". Name both halves and the fields each uses.
12. What does `AlwaysPullImages` do to your `imagePullPolicy`? What security problem does it solve?
13. Is `AlwaysPullImages` enabled by default? Why does that explain real-world behaviour?
14. Why does the API server flag show only `NodeRestriction` when many plugins are enabled?
15. What happens to pod creation if you disable the `ServiceAccount` plugin? What does the pod lose?
16. What are `MutatingAdmissionWebhook` and `ValidatingAdmissionWebhook` — plugins or controllers? What do they call?
17. Define a webhook in one sentence, with a non-Kubernetes example.
18. What can a webhook **authorizer** see? What can it **not** see — and what can't it therefore check?
19. Which requirement from Day 35 was corrected here, and what is the fix?
20. Give two things OPA can do as an authorizer that RBAC cannot.
21. Why must OPA return `NoOpinion` on success rather than `Allow`?
22. What is the standard production combination of authorization modes plus admission?
23. "All pods must have `team` and `env` labels" — mutating or validating? What about "inject them if missing"?
24. Walk the order of `NamespaceLifecycle, LimitRanger, ServiceAccount, MutatingAdmissionWebhook, ValidatingAdmissionWebhook, ResourceQuota` for a pod creation.

---

## What's Next (Day 39)

- **Custom Resource Definitions (CRDs)** — extending the Kubernetes API with your own resource types, and how operators use them.

---

*End of Day 38 notes.*
