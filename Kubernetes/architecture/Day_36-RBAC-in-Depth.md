# RBAC in Depth — Roles, Bindings, ClusterRoles & ClusterRoleBindings (Day 36)

> Source: Day 36 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: **RBAC authorization** end to end — the four objects, how scoping actually works, **verbs**, and three demos that separate the combinations people confuse.
> Prerequisite: **Day 34** (create a user with a CSR — you need one to follow along) and **Day 35** (API groups, authorization modes, the `Allow`/`Deny`/`NoOpinion` rule).
> Next: **ServiceAccounts** (Day 37).

---

## 1) What Is RBAC?

> **RBAC = Role-Based Access Control** — a mechanism to grant permissions to Kubernetes resources **based on roles**.

### The organisational analogy

In a real production team you don't grant permissions person by person. You define **roles**:

```
Infrastructure engineers
Developers
DevOps engineers
   ├── Jenkins
   ├── Kubernetes
   └── CI/CD
Security team
```

Each role gets a bundle of permissions. People **fill** roles, and permissions follow.

> Without role abstraction you'd need a unique permission set per human. With it, you manage a handful of roles — and **an audit becomes "who holds which role?"** instead of "what can this person do?"

### Who enforces it?

| Step | Performed by |
|---|---|
| **Authentication** | The **API server** (Day 34 handed us a user with a certificate) |
| **Authorization** | The **API server** — *unless* you outsource it via **webhook** (Day 35) |

This lecture assumes **RBAC**: the API server decides, using the objects we're about to create.

---

## 2) Namespaced vs Cluster-Scoped — the Foundation

Everything about RBAC scoping descends from one column:

```bash
kubectl api-resources
```

```
NAME            SHORTNAMES   APIVERSION   NAMESPACED   KIND
pods            po           v1           true         Pod
deployments     deploy       apps/v1      true         Deployment
daemonsets      ds           apps/v1      true         DaemonSet
nodes           no           v1           false        Node
persistentvolumes pv         v1           false        PersistentVolume
clusterroles                 rbac.authorization.k8s.io/v1  false  ClusterRole
```

| `NAMESPACED` | Meaning | Examples |
|---|---|---|
| **`true`** | The resource lives **inside a namespace**; if you don't name one, it goes to `default` | `pods`, `deployments`, `daemonsets`, `services`, `configmaps`, **`serviceaccounts`**, `pvc`, `roles` |
| **`false`** | **Cluster-scoped / cluster-wide** — belongs to the whole cluster | **`nodes`**, **`pv`**, `clusterroles`, `storageclasses`, `csr`, `namespaces` |

> `kubectl get nodes` has no `-n` flag for a reason: **nodes aren't in a namespace.** Same for PVs (Day 27).

---

## 3) The Four Objects

### Role — permissions **within one namespace**

> **A Role defines a set of permissions within a namespace.** It **cannot** be used for cluster-scoped objects.

- ✅ Can govern `pods`, `deployments` — namespaced things.
- ❌ **Cannot** govern `nodes`, `pv` — those need a ClusterRole.

### RoleBinding — **who gets the Role, in this namespace**

> **Associates a Role *or* a ClusterRole with specific users, groups, or service accounts, within that namespace.**

Two things to notice in that sentence:

1. It binds **subjects** → **role**.
2. It can reference a **ClusterRole** — that "or" is the whole of **Demo 3**.

### ClusterRole — cluster-wide, or reusable

> **Like a Role, but the permissions can apply cluster-wide *or* be reused across multiple namespaces.**

Two distinct purposes:

| Purpose | Why ClusterRole |
|---|---|
| Grant permissions on **cluster-scoped** resources (`nodes`, `pv`) | A Role can't — those resources aren't in any namespace |
| Grant permissions on **namespaced** resources **in many namespaces** | One ClusterRole instead of N identical Roles |

### The misconception, killed properly

> *"Deployments are namespaced, so I can't put them in a ClusterRole."* — **False.**

> **You can create ClusterRoles for *all* resources** — namespaced or not. What changes is **how you bind them**.

| Want | Use |
|---|---|
| Deployments in **one** namespace | Role + RoleBinding |
| Deployments in **specific** namespaces (e.g. 10 of 20) | **ClusterRole** + a **RoleBinding per namespace** |
| Deployments in **all** namespaces | **ClusterRole** + **ClusterRoleBinding** |

> The **ClusterRole** defines *what*; the **binding type** decides *where*. This single sentence is worth the whole lecture.

### ClusterRoleBinding — **everywhere**

> **Binds a ClusterRole to users, groups, or service accounts at cluster level, granting access across the entire cluster.**

No `namespace` field exists on a ClusterRoleBinding — that's not an oversight, it's the definition.

---

## 4) Verbs — the "What Actions" Half

> **Verbs are the actions you can perform on a resource.**

| Verb | Allows |
|---|---|
| **`get`** | Read **one** named object |
| **`list`** | Read **all** objects of a kind (what `kubectl get pods` needs) |
| **`watch`** | Stream changes (`kubectl get pods -w`, controllers) |
| **`create`** | Create objects |
| **`update`** | Replace an object |
| **`patch`** | Partially modify |
| **`delete`** | Delete one object by name |
| **`deletecollection`** | Delete many at once |

### Which verbs does *this* resource support?

> `kubectl api-resources` **`-o wide`** adds a **VERBS** column — the authoritative answer per resource.

```bash
kubectl api-resources -o wide
```

```
NAME        ...   VERBS
pods        ...   create,delete,deletecollection,get,list,patch,update,watch
bindings    ...   create
```

> Some resources support **only `create`** (e.g. `bindings`, `tokenreviews`) — you simply cannot grant `list` on them, so writing it in a Role achieves nothing.

### Subresources need their own entries

Not in this lecture, but the same mechanism: `pods/log` and `pods/exec` are **subresources**. To let someone run `kubectl logs`, you grant `get` on **`pods/log`**, not just `pods`. Worth knowing before it bites you.

---

## 5) Demo 1 — Role + RoleBinding in a Namespace

### The manifest (`role.yaml`)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: workload-editor
  namespace: dev                     # the Role is scoped here
rules:
  - apiGroups: [""]                  # "" = core group → pods
    resources: ["pods"]
    verbs: ["create", "list"]
  - apiGroups: ["apps"]              # deployments live in apps/v1
    resources: ["deployments"]
    verbs: ["create", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: bind-workload-editor
  namespace: dev
subjects:
  - kind: User
    name: seema
    apiGroup: rbac.authorization.k8s.io
  - kind: Group
    name: junior-admins
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: workload-editor
  apiGroup: rbac.authorization.k8s.io
```

### Reading it

| Element | Explanation |
|---|---|
| **`apiVersion: rbac.authorization.k8s.io/v1`** | The RBAC **named** group (Day 35). Authorization has **two** groups — this is the object-definition one; the other (`authorization.k8s.io`) is for reviews |
| **`rules` is plural** | A Role holds **many** rules |
| **Two rules** | Pods and deployments — a "workload editor" bundle |
| **`apiGroups: [""]`** | Empty string = **core** → `pods` (confirmed via `api-resources`: pods are `v1`) |
| **`apiGroups: ["apps"]`** | Deployments are `apps/v1` |
| **`verbs: [create, list]`** | Only these two — **no `get`**, **no `delete`** |
| **`subjects` is plural** | One binding can serve **many** identities |
| **`---`** | YAML document separator — two objects, one file |

### The `roleRef` direction

```
RoleBinding  ──roleRef──►  Role          (which permissions)
             └─subjects─►  User/Group/SA (who receives them)
```

> **A Role is a standalone object.** Naming it `workload-editor` gives **nobody** anything. **Only the binding realizes the Role's power.** (Day 34 made the same point: `seema-role` didn't belong to Seema until `seema-binding` existed.)

### The service-account `apiGroup` trap

| `subjects[].kind` | `apiGroup` must be |
|---|---|
| `User` | **`rbac.authorization.k8s.io`** |
| `Group` | **`rbac.authorization.k8s.io`** |
| **`ServiceAccount`** | **`""`** (empty string) |

**Why:** ServiceAccounts are a **core-group** resource — and the core group has **no name** in the API (Day 35). Get this wrong and the binding silently matches nothing.

### Apply — and hit the namespace error

```bash
kubectl apply -f role.yaml
# Error from server (NotFound): namespaces "dev" not found
```

> **Roles and RoleBindings require their namespace to exist.** `kubectl apply` will **not** create it for you (same lesson as Day 29's DaemonSet demo).

```bash
kubectl create ns dev              # ns = short name
kubectl apply -f role.yaml
# role.rbac.authorization.k8s.io/workload-editor created
# rolebinding.rbac.authorization.k8s.io/bind-workload-editor created
```

### Inspect

```bash
kubectl get roles                       # "No resources found" — you're in default!
kubectl get roles -n dev
kubectl describe role workload-editor -n dev
```

> The `-n dev` omission is the same trap as Day 29. Fix it permanently by setting the **context's default namespace**:

```bash
kubectl config set-context --current --namespace=dev
kubectl config get-contexts            # NAMESPACE column now shows dev
```

Now `kubectl get roles` works without `-n`. **This is how real work flows** — you change context, change namespace, and the commands get short.

```bash
kubectl get rolebindings
kubectl describe rolebinding bind-workload-editor
kubectl get rolebinding bind-workload-editor -o yaml     # works for any object
```

### Verify as the admin — `kubectl auth can-i`

> **It is your responsibility to confirm the permissions you granted actually work.** Do it **before** the user does.

```bash
kubectl auth can-i create pod -n dev
# yes

kubectl auth can-i create pod -n prod
# no                     ← the Role is namespaced to dev
```

### Now test as Seema

```bash
kubectl config use-context seema@kind-my-second-cluster-context
kubectl get pods
# Error ... Forbidden ... in the namespace "default"
```

> **Why?** Seema's context defaults to `default`, but the permissions live in **`dev`**. **Authorization is namespace-scoped** — the identity doesn't travel with access.

```bash
kubectl get pods -n dev
# No resources found in dev namespace.        ← allowed (list granted)

kubectl get deploy -n dev                     # allowed
kubectl create deploy my-deploy --image=nginx -n dev
# deployment.apps/my-deploy created           ← create granted

kubectl delete deployment my-deploy -n dev
# Error ... Forbidden                          ← delete NOT granted
```

> **Only the verbs you listed apply.** `create` + `list` means exactly that — no `get` (single object), no `delete`, no `update`.

---

## 6) Demo 2 — ClusterRole + ClusterRoleBinding

### The manifest (`clusterrole.yaml`)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-reader                  # NO namespace field
rules:
  - apiGroups: [""]                  # nodes are core group
    resources: ["nodes"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: bind-node-reader             # NO namespace field
subjects:
  - kind: User
    name: seema
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole                  # ← must be ClusterRole
  name: node-reader
  apiGroup: rbac.authorization.k8s.io
```

### The structural difference: **no namespace anywhere**

> *"We have not specified any namespace anywhere here — because ClusterRoles are for cluster-scoped resources… and for namespaced resources too, but we do not specify any namespace."*

`kubectl apply` → `created`, with **no namespace prerequisite** to satisfy.

### Test as Seema

```bash
kubectl config use-context seema@kind-my-second-cluster-context

kubectl get pv
# Error ... Forbidden          ← PVs are cluster-scoped, but no rule grants them

kubectl get nodes
# NAME ... STATUS ...          ← allowed, and no -n needed
```

> **`get nodes` needs no `-n`** — because nodes are cluster-scoped, exactly as `api-resources` said (`NAMESPACED: false`).

### Skipped deliberately

`kubectl get clusterrole` / `get clusterrolebinding` — same shape as the Role/`get` commands from Demo 1, so the lecture skips them. (They're cluster-scoped, so no `-n`.)

---

## 7) Demo 3 — ClusterRole + RoleBinding (the important one)

**The requirement:** grant `pods` + `deployments` access in a **subset** of namespaces.

### The scenario, stated precisely

> *20 namespaces. Access needed in **10** of them.*

| Approach | Result |
|---|---|
| 10 Roles + 10 RoleBindings | Works, but **duplicated policies** drift apart |
| 20 Roles + 20 RoleBindings | Worse |
| **1 ClusterRole + 10 RoleBindings** | **One policy source, per-namespace grants** ✅ |
| 1 ClusterRole + **1 ClusterRoleBinding** | Grants **all 20** ❌ too much |

> **A ClusterRole is the reusable definition. A RoleBinding is the per-namespace grant.** That's the pattern the CKA expects you to know.

### The manifest (`clusterrole-rolebinding.yaml`)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prod-workload-admin
rules:
  - apiGroups: [""]
    resources: ["pods", "deployments"]     # pods are core...
    verbs: ["create", "delete", "update", "patch"]
  # (deployments would be a separate rule with apiGroups: ["apps"])
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding                          # ← NOT a ClusterRoleBinding
metadata:
  name: bind-prod-workload-admin
  namespace: prod                          # ← the namespace does the scoping
subjects:
  - kind: User
    name: seema
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole                        # ← references the ClusterRole
  name: prod-workload-admin
  apiGroup: rbac.authorization.k8s.io
```

### Why a RoleBinding and not a ClusterRoleBinding?

> **A ClusterRoleBinding has no `namespace` field** — so it cannot be limited. It grants **all 20** namespaces.
>
> **A RoleBinding has a namespace** — so a ClusterRole bound with a RoleBinding grants access **only in that namespace**.

To cover 10 namespaces: **one ClusterRole + 10 RoleBindings.**

### The four combinations (the exam table)

| Definition | Binding | Grants | Scope |
|---|---|---|---|
| **Role** | **RoleBinding** | Role's rules | **One namespace** (Demo 1) |
| **ClusterRole** | **ClusterRoleBinding** | ClusterRole's rules | **All namespaces** + cluster-scoped resources (Demo 2) |
| **ClusterRole** | **RoleBinding** | ClusterRole's rules | **Only the RoleBinding's namespace** (Demo 3) ✅ |
| **Role** | **ClusterRoleBinding** | ❌ **impossible** — `roleRef.kind` on a ClusterRoleBinding must be `ClusterRole` | — |

> That last row is a legitimate exam trap: **you cannot bind a namespaced Role cluster-wide.** If you need cluster-wide, the definition must be a ClusterRole.

### Apply — the namespace prerequisite again

```bash
kubectl apply -f clusterrole-rolebinding.yaml
# Error: namespaces "prod" not found

kubectl create ns prod
kubectl apply -f clusterrole-rolebinding.yaml
# clusterrole ... created / rolebinding ... created
```

### Test as Seema

```bash
kubectl config use-context seema@kind-my-second-cluster-context
kubectl config set-context --current --namespace=prod

kubectl get pods
# Forbidden        ← get/list were NOT granted
kubectl get deploy
# Forbidden        ← same

kubectl create deploy my-deploy --image=nginx
# deployment.apps/my-deploy created          ← create IS granted

kubectl delete deployment my-deploy
# deployment.apps "my-deploy" deleted        ← delete IS granted
```

> **Note the shell behaviour:** tab-completion stops working in this context — completion is implemented with `get`/`list` calls. **No `get` → no autocomplete.** That's not a bug; it's a visible symptom of a least-privilege grant.

### Cleanup (with the standing warning)

```bash
kubectl config use-context kind-my-second-cluster
kubectl config set-context --current --namespace=default

kubectl delete ns dev
kubectl delete ns prod
```

> ⚠️ **Deleting a namespace deletes everything inside it.** *"Be very cautious… if you are running this in production, be extra cautious."*

---

## 8) Verifying Grants — `kubectl auth can-i`

The lecture's insistence: **verify as the admin, immediately after granting.**

```bash
# As the current (admin) user — but the question is about the RESOURCE, not you
kubectl auth can-i create pod -n dev

# About a specific user, without switching context
kubectl auth can-i create pod --as seema -n dev
kubectl auth can-i create pod --as seema -n prod

# Everything a user can do in a namespace
kubectl auth can-i --list --as seema -n dev

# Cluster-scoped question
kubectl auth can-i get nodes --as seema
```

| Command | Answers |
|---|---|
| `can-i <verb> <resource>` | *"May I…?"* for **your** identity |
| `--as <user>` | *"…may **they**…?"* — impersonation; admin-only |
| `--list` | Dump every allowed verb/resource pair |

> `--as` is faster and safer than switching contexts, and it leaves your kubeconfig untouched.

### `can-i` proved the namespace scoping in Demo 1

```bash
kubectl auth can-i create pod -n dev     # yes
kubectl auth can-i create pod -n prod    # no
```

Same user, same verb, same resource — **different answer because of the namespace.** That's RBAC scoping in one command.

---

## 9) Best Practices

| Practice | Why |
|---|---|
| **Grant the minimum verbs** | Demo 1's `create`+`list` was deliberate; `delete` was withheld |
| **Prefer groups over individuals** | `junior-admins` scales; 50 per-person bindings don't |
| **One ClusterRole per function, RoleBindings per namespace** | Single source of policy, per-namespace grants (Demo 3) |
| **Always verify with `can-i`** | The grant you *think* you made isn't the grant until it says `yes` |
| **Never bind to `system:masters`** | It bypasses RBAC entirely — the "give me root" shortcut that defeats the model |
| **Don't grant `*` verbs/resources** | `verbs: ["*"]` looks convenient and audits terribly |
| **Remember: no `get` → no tab completion** | A practical signal you under-granted |
| **Namespace deletion is irreversible** | `delete ns` takes everything in it |
| **ClusterRoleBindings are global — treat as production changes** | One binding can grant every namespace |

### The `system:` groups you'll meet

Kubernetes ships built-in roles (`view`, `edit`, `admin`, `cluster-admin` as **ClusterRoles**). Binding `cluster-admin` is the nuclear option; `view`/`edit` are namespace-appropriate. Knowing they exist saves you writing Roles for common cases.

---

## 10) Key Takeaways

1. **RBAC = Role-Based Access Control** — permissions attach to **roles**, and identities **fill** roles.
2. **Authentication ≠ authorization.** The API server does both (unless a **webhook** is in the chain).
3. **`kubectl api-resources` NAMESPACED column governs everything.** `true` = in a namespace; `false` = cluster-wide.
4. **Cluster-scoped examples:** `nodes`, `pv`, `clusterroles`, `storageclasses`, `csr`, `namespaces`. **Namespaced:** `pods`, `deployments`, `serviceaccounts`, `pvc`, `roles`.
5. **Role = permissions inside one namespace** and **cannot** govern cluster-scoped resources.
6. **RoleBinding = subjects → role, inside one namespace.** It can reference a **Role or a ClusterRole**.
7. **ClusterRole = cluster-wide permissions, or a reusable definition.**
8. **A ClusterRole CAN contain namespaced resources** (`pods`, `deployments`). The **binding** decides the scope.
9. **ClusterRoleBinding = cluster-wide grant**, has **no namespace field**, and its `roleRef.kind` **must be `ClusterRole`**.
10. **The magic combo for a namespace subset:** **1 ClusterRole + N RoleBindings**.
11. **Demo 1:** Role + RoleBinding in `dev`; `apiGroups: [""]` for pods, `["apps"]` for deployments; only `create`+`list` → `delete` was `Forbidden`.
12. **Demo 2:** ClusterRole + ClusterRoleBinding for `nodes`; `get nodes` worked, `get pv` didn't (no rule).
13. **Demo 3:** ClusterRole + RoleBinding in `prod`; `get` denied but `create`/`delete` allowed — proving verbs are enforced individually.
14. **`roleRef` is the link** — a Role on its own grants nothing until a binding references it.
15. **`subjects[].apiGroup` is `""` for ServiceAccounts** (core group) and `rbac.authorization.k8s.io` for Users/Groups.
16. **Roles and RoleBindings require an existing namespace** — `apply` won't create it.
17. **`-n` is mandatory unless the context sets a default** — use `kubectl config set-context --current --namespace=`.
18. **`list` is what `kubectl get pods` needs**; `get` alone only fetches one named object.
19. **Check available verbs with `kubectl api-resources -o wide`.**
20. **Verify with `kubectl auth can-i`** — including `--as <user>` and `--list`.
21. **Least privilege has visible symptoms** — missing tab completion is one.
22. **A namespace-scoped grant is invisible from another namespace**, even for the same user and verb.

---

## 11) Essential Commands

```bash
# --- Discover scoping and verbs ---
kubectl api-resources
kubectl api-resources -o wide                 # VERBS column
kubectl api-resources | Select-String -Pattern "nodes|pods|persistentvolumes"

# --- Apply RBAC (namespace must exist!) ---
kubectl create ns dev
kubectl apply -f role.yaml
kubectl apply -f clusterrole.yaml

# --- Inspect ---
kubectl get roles -n dev
kubectl describe role workload-editor -n dev
kubectl get rolebindings -n dev
kubectl describe rolebinding bind-workload-editor -n dev
kubectl get clusterrole node-reader
kubectl get clusterrolebinding bind-node-reader
kubectl get role workload-editor -o yaml

# --- Namespace context management ---
kubectl config get-contexts
kubectl config use-context seema@kind-my-second-cluster-context
kubectl config set-context --current --namespace=dev

# --- Verify permissions ---
kubectl auth can-i create pod -n dev
kubectl auth can-i create pod --as seema -n dev
kubectl auth can-i --list --as seema -n dev
kubectl auth whoami

# --- Test as the user ---
kubectl get pods -n dev
kubectl create deploy my-deploy --image=nginx -n dev
kubectl delete deployment my-deploy -n dev

# --- Cleanup (careful!) ---
kubectl delete ns dev
```

### Demo 1 — Role + RoleBinding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: { name: workload-editor, namespace: dev }
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["create", "list"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["create", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: { name: bind-workload-editor, namespace: dev }
subjects:
  - { kind: User,  name: seema,         apiGroup: rbac.authorization.k8s.io }
  - { kind: Group, name: junior-admins, apiGroup: rbac.authorization.k8s.io }
roleRef: { kind: Role, name: workload-editor, apiGroup: rbac.authorization.k8s.io }
```

### Demo 2 — ClusterRole + ClusterRoleBinding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: { name: node-reader }
rules:
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: { name: bind-node-reader }
subjects:
  - { kind: User, name: seema, apiGroup: rbac.authorization.k8s.io }
roleRef: { kind: ClusterRole, name: node-reader, apiGroup: rbac.authorization.k8s.io }
```

### Demo 3 — ClusterRole + RoleBinding (subset of namespaces)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: { name: prod-workload-admin }
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["create", "delete", "update", "patch"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["create", "delete", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: { name: bind-prod-workload-admin, namespace: prod }
subjects:
  - { kind: User, name: seema, apiGroup: rbac.authorization.k8s.io }
roleRef: { kind: ClusterRole, name: prod-workload-admin, apiGroup: rbac.authorization.k8s.io }
```

---

## 12) Quick Self-Check

1. Define RBAC in one sentence. Why are roles better than per-person permissions?
2. Who performs authorization in an RBAC cluster? What changes that?
3. Which `kubectl` command tells you whether a resource is namespaced?
4. Name three cluster-scoped and three namespaced resources.
5. Can a Role grant access to `nodes`? Why not?
6. What can a RoleBinding reference — Role only, ClusterRole only, or both?
7. Can a ClusterRole contain `deployments`? What determines whether access is one namespace or all?
8. What field does a ClusterRoleBinding **not** have, and why does that matter?
9. You need `pods` access in 10 of 20 namespaces. What's the minimal object set?
10. Why is "Role + ClusterRoleBinding" impossible?
11. Why did Demo 1's Role fail to apply the first time?
12. In Demo 1, why did Seema's `kubectl get pods` fail while `-n dev` worked?
13. Which two verbs were granted in Demo 1, and which one did the delete attempt prove was missing?
14. In Demo 2, why did `get pv` fail but `get nodes` succeed?
15. In Demo 3, `get` was denied while `create` and `delete` worked. What does that prove about verbs?
16. Why does tab completion break when a user lacks `get`/`list`?
17. What `apiGroup` do you write for a ServiceAccount subject? Why?
18. Which command verifies a grant as another user without switching context?
19. Why is binding `system:masters` a bad idea?
20. What's the risk of `kubectl delete ns`?

---

## What's Next (Day 37)

- **ServiceAccounts** — how Kubernetes gives **workloads** (not humans) an identity, how tokens are projected into pods, and how RBAC applies to them.

---

*End of Day 36 notes.*
