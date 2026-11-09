# Ephemeral Storage in Kubernetes — emptyDir & downwardAPI — Complete Notes (Day 26)

> Source: Day 26 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: **Ephemeral** storage only — `emptyDir` volumes and the **downwardAPI**, with a short preview of ConfigMaps & Secrets.
> Deliberate split: **persistent** storage (PV, PVC, StorageClass) is Day 27.
> Prerequisite: Day 21 (multi-container pods, shared storage), Day 24 (read-only vs writable layers), Day 25 (CSI).

---

## 1) What Is Ephemeral Storage?

> **Anything temporary that goes away when the pod is terminated is ephemeral storage.**

The key phrase is **lifetime of the pod** — not the lifetime of the container, and certainly not forever.

Storage in Kubernetes splits cleanly in two:

| | **Ephemeral** | **Persistent** |
|---|---|---|
| Lifetime | Tied to the **pod** | **Independent** of the pod |
| Survives pod deletion? | **No** | **Yes** |
| Examples | `emptyDir`, `downwardAPI`, container writable layer | PV / PVC, cloud disks, NFS |
| Covered | **Today (Day 26)** | Day 27 |

---

## 2) `emptyDir` — The Four Properties

### Property 1 — Exists for the lifetime of the pod

Create a pod with an `emptyDir` volume → the volume is **deleted the moment the pod is deleted**.

"Empty at creation" is where the name comes from: the directory starts empty, and its contents live only as long as the pod.

### Property 2 — Enables data sharing between containers **in a pod**

This is the whole point, and the natural objection is:

> *"But Varun, we've been using pods since the beginning of the course, writing data, deleting the pod, and the data was gone. What's special about `emptyDir`?"*

**The difference: `emptyDir` lets containers in the same pod share data.**

Recall Day 21: a pod's containers share **networking** and — only if you mount it — **storage**.

```
Volume given to the POD
        │
        ├── mounted into container 1  → only container 1 sees it
        ├── mounted into container 2  → now 1 and 2 share it
        └── mounted into container 3  → all three share it
```

You **choose** how many containers get the mount. Mount it into all of them and they share the same data.

### Property 3 — Each pod replica gets its own unique `emptyDir`

- A Deployment with **5 replicas** spread across **3 nodes** → **5 separate `emptyDir` volumes**.
- An `emptyDir` **cannot** be shared between **two different pods** — ever.
- Sharing is possible **only among containers of the same pod**, and only for the containers that mounted it.

```
Pod A ── emptyDir-A ── containers A1, A2 (shared within pod A)
Pod B ── emptyDir-B ── containers B1, B2 (shared within pod B)
                 ↑
        A and B never see each other's data
```

### Property 4 — Uses host storage

- `emptyDir` is backed by the **node's local disk** by default.
- **How much** you get: as much as the host can support. If your host has 100 GB, allocating 2 GB of scratch space is straightforward.
- It also runs on the **node** — so it's fast, which is why it suits caching (`medium: Memory` makes it faster still).

#### The Docker Desktop nuance (why Day 24 matters here)

On **Linux/Ubuntu**, the "host storage" is the **actual host** — install Docker Engine directly and that's that.

On **macOS/Windows**, Docker Desktop creates a **lightweight Linux VM** and installs the engine inside it. So:

| Platform | What "host storage" really is |
|---|---|
| Ubuntu (Docker Engine native) | The real host filesystem |
| macOS / Windows (Docker Desktop) | The **Linux VM's** filesystem — which itself sits on your base storage |

> The distinction matters in practice: the VM *is* your Docker host. (Same reason `cd /var/lib/docker/...` failed in Day 24.)

### `emptyDir` vs the writable layer (the Day 24 contrast)

| | Writable layer | `emptyDir` |
|---|---|---|
| Created per | **Container** | **Pod** |
| Shared between containers? | **Never** | **Yes**, if mounted into each |
| Deleted when | Container dies | **Pod** dies |
| Backed by | Storage driver | Node disk (or RAM) |

**Concretely** (Day 24's diagram, re-used):

```
Pod with 3 containers, same image
   container1 → writable layer 4 MB  (private)
   container2 → writable layer 10 MB (private)
   container3 → writable layer 6 MB  (private)
        └── shared read-only image layers

Add an emptyDir mounted into all three:
   anything written under the mount path → visible to ALL three
   writable layers still exist and are still private
```

**Both are true at once.** Containers keep their own private writable layers *and* gain a shared, pod-scoped directory.

---

## 3) `emptyDir` Use Cases

| Use case | Why `emptyDir` fits |
|---|---|
| **1. Scratch space** | Temporary working storage. Upper bound = whatever the host supports (e.g. 100 GB host → give it 2 GB of scratch) |
| **2. Caching** | Node-local disk is **fast**; `medium: Memory` is **faster** — and caching needs speed above all |
| **3. Temporary persistence** | Logs or files that must survive a container restart **within** the pod's life, but not the pod's deletion |

### Use case 2 in more depth — why "host storage" means "fast"

Your laptop's **internal** SSD is fast. A **USB drive** plugged in is external and slower. Same with servers:

- A big server's **internal storage** is directly attached → fast access.
- External/networked storage is slower.

Caching wants the fastest thing available, so `emptyDir` (node-local or RAM) is the right pick.

---

## 4) The `emptyDir` YAML — Anatomy

This structure is **the foundation of all Kubernetes storage** — ephemeral and persistent.

### Step 1 — A pod skeleton

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-example
spec:
  containers:
    - name: busybox
      image: busybox
      command: ["sh", "-c", "sleep 3600"]      # 60 minutes
```

### Step 2 — Give a volume to the **pod**

```yaml
spec:
  volumes:
    - name: temp-storage
      emptyDir: {}
```

- The volume is declared **under `spec`** — at **pod** level, not inside the container.
- `name:` is how you'll refer to it later.
- `emptyDir: {}` is the **type**. When you move to persistent storage this key changes (`hostPath:`, `persistentVolumeClaim:`, etc.) — **the rest of the pattern stays identical**.

> **`{}` means "take every default".**
> - `medium` defaults to `""` → **node disk**
> - `sizeLimit` defaults to **unlimited**

### Step 3 — Mount it into a **container**

```yaml
    volumeMounts:
      - name: temp-storage
        mountPath: /data
```

- `name` → **which** volume (must match a volume in `spec.volumes`)
- `mountPath` → **where inside the container**

`volumeMounts` is a **list** — create four volumes and add four entries.

### The full manifest

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-example
spec:
  volumes:
    - name: temp-storage
      emptyDir: {}
  containers:
    - name: busybox
      image: busybox
      command: ["sh", "-c", "sleep 3600"]
      volumeMounts:
        - name: temp-storage
          mountPath: /data
```

### The mental model (worth memorising)

```
1. Give the volume to the POD        →  spec.volumes
2. Mount it into each CONTAINER      →  container.volumeMounts
```

> The instructor's framing: *"If you understand this as a foundational concept, writing YAML is a play. It's 60% of Kubernetes storage."*

### Other `emptyDir` options

| Option | Meaning |
|---|---|
| `emptyDir: {}` | All defaults — node disk, unlimited |
| `medium: Memory` | **RAM-backed (tmpfs)** — fastest, counts toward memory |
| `sizeLimit: 2Gi` | Cap the volume's size |

```yaml
  volumes:
    - name: cache
      emptyDir:
        medium: Memory
        sizeLimit: 500Mi
```

> `medium: Memory` is the Kubernetes equivalent of Docker's `--tmpfs` (Day 24): fast, and it consumes **memory** rather than disk.

### Tooling tip — schema autocomplete

The lecture uses VS Code with **Kubernetes**, **Docker**, and **YAML** extensions:

- **`Ctrl+Space`** (macOS) / **`Alt+Space`** (Windows) → field suggestions inside any YAML key.
- Works for *all* Kubernetes YAML, not just `emptyDir`.

> **But the exam has no VS Code.** No `Ctrl+Space` there. Learn to navigate the docs:
> `kubernetes.io/docs` → search **volumes** → use the sidebar (or `Ctrl+F` for `emptyDir`) → read the field options.
> The instructor's advice: *don't be afraid to refer to documentation.*

---

## 5) Demo 1 — Single Container with `emptyDir`

```bash
kubectl apply -f emptydir.yaml
kubectl get pods
```

The pod runs. A single container doesn't demonstrate sharing, though — so the second demo adds another container.

(Also note the editor's own warning: **"one or more containers do not have resource limits — this could starve other processes."** That's Day 19 talking. Set requests/limits in production.)

---

## 6) Demo 2 — Sharing Data Between Two Containers

### The manifest (`emptydir.yaml`, revised)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-example
spec:
  volumes:
    - name: temp-storage
      emptyDir: {}
  containers:
    - name: busybox
      image: busybox
      command: ["sh", "-c", "sleep 3600"]
      volumeMounts:
        - name: temp-storage
          mountPath: /data

    - name: busybox-2
      image: busybox
      command: ["sh", "-c", "sleep 3600"]
      volumeMounts:
        - name: temp-storage          # SAME volume
          mountPath: /data             # same or different path — your call
```

**The only thing that creates sharing is that `name: temp-storage` appears in both `volumeMounts` blocks.**

### Apply and explore

```bash
kubectl delete pod emptydir-example --force
kubectl apply -f emptydir.yaml
kubectl get pods            # ContainerCreating → 2/2 Running
```

### Write from container 1

```bash
kubectl exec -it emptydir-example -c busybox -- sh

# inside container 1:
ls -lr /data                       # the directory already exists (mounted empty)
cd /data
echo "this is my file" > my-file.txt
cat my-file.txt                    # this is my file
exit
```

### Read from container 2

```bash
kubectl exec -it emptydir-example -c busybox-2 -- sh

# inside container 2:
cd /data
ls                                 # my-file.txt  ← it's here
cat my-file.txt                    # this is my file
exit
```

**Written in one container, read in the other.** The file is not copied — both containers are looking at the **same bytes** on the node's disk.

### Reading the commands

| Part | Meaning |
|---|---|
| `kubectl exec -it <pod> -c <container> -- sh` | Exec into a **specific** container |
| `-c busybox` | Required when the pod has more than one container |
| *(if `-c` is omitted with multiple containers)* | kubectl defaults to the **first** container |

### Cleanup

```bash
kubectl delete pod emptydir-example --force
```

`--force` skips the grace period (Day 22). The `emptyDir` is **destroyed with the pod**.

### What this proved

> Containers in a pod can share storage **as long as they mount it**. Scratch data written under `/data` was visible to both. Their private writable layers were untouched and still separate.

---

## 7) The `downwardAPI` — Injecting Pod Metadata

### Definition

> **The downwardAPI allows pods to access metadata about themselves.**

Metadata includes:

- Pod **name**
- **Namespace**
- **Labels**
- **Annotations**
- **Resource limits**
- …and more

### The problem it solves

Your application runs **inside** a container. It knows **nothing** about the pod around it:

- It doesn't know the pod's **name**.
- It doesn't know which **namespace** it's in.
- It doesn't know the **resource limits** set on it.
- It doesn't know the **labels** or **annotations** attached to it.

*"But Varun, my application is running fine — why would it want to know any of that?"*

### The real reason: sidecars (Day 21 callback)

Picture a **sidecar container** doing **monitoring** — collecting metrics for the app.

> **What use are those metrics if you don't know which pod they belong to?**

If you want telemetry broken down **by namespace** ("show me app-one's stats"), you need to know **which pods are in app-one**. Without pod identity, the data is meaningless.

Same for **logging**. Monitoring and logging sidecars **often use downwardAPI volumes** to present exactly this context.

So: sometimes it's your app that wants the metadata; more often it's the helpers **around** your app.

### Why it also offloads the API server

Normally, to learn what's running you'd run:

```bash
kubectl get pods -n kube-system      # names of pods
kubectl get namespaces               # namespaces
```

Those are **`kubectl` client → API server** queries.

Without the downwardAPI, a container wanting its own pod name would have to:

1. Send an **HTTP request to the API server**, and
2. Supply **authentication + authorization** (you cannot reach a cluster without them).

If every container did that continuously, the **API server gets hammered** — and it has plenty of other responsibilities.

> **The downwardAPI offloads the API server:** metadata is delivered locally, from the kubelet, no API round-trip, no credentials.

### Two delivery mechanisms

| Mechanism | How |
|---|---|
| **Environment variables** | `valueFrom.fieldRef.fieldPath` |
| **Files (a volume)** | `downwardAPI` volume with `items` |

Both are demonstrated below.

### Use cases

| Use case | Explanation |
|---|---|
| **Dynamic configuration** | A logging/monitoring helper is told where the API server is **without hardcoding or extra code** |
| **Self-awareness** | A sidecar knows its own pod name, namespace, labels, and resource limits automatically |
| **App-owner requests** | If an application owner asks for pod metadata, you already have a solution |

---

## 8) Demo 3 — downwardAPI via Environment Variables

### The manifest (`downward-api-1.yaml`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: downwardapi-example
  labels:
    app: demo
spec:
  containers:
    - name: metadata-container
      image: busybox
      command: ["env"]                 # print all env vars
      env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
```

### Walking through it

- `command: ["env"]` — the container **prints every environment variable**. That's how we'll see the injected values.
- `env:` is a **list** → define as many variables as you like.
- `fieldRef.fieldPath` is the pointer into the pod's own metadata:
  - `metadata.name` → the pod's name
  - `metadata.namespace` → the pod's namespace

> `metadata.namespace` reads like a path: look at `metadata`, then find `namespace`. Later the course covers **JSONPath** properly; this primitive form is enough for now.

### A note on the namespace

`metadata.namespace` **isn't in the manifest** — but Kubernetes autofills it. Since we didn't specify one, the pod lands in **`default`**.

Verify:

```bash
kubectl apply -f downward-api-1.yaml
kubectl get pods

kubectl get pod downwardapi-example -o yaml
```

Scroll to `metadata:` — you'll see `namespace: default` **auto-populated**.

### Read the output

```bash
kubectl logs downwardapi-example
```

```
POD_NAMESPACE=default
POD_NAME=downwardapi-example
...
```

Both values were injected **from the pod's own metadata** at container start.

> **Note:** the manifest names the variables `pod-name` / `pod-namespace`. Environment variable names in Kubernetes manifests conventionally use `UPPER_CASE`; kubectl/env will show whatever you declare.

---

## 9) Demo 4 — downwardAPI as Files (a Volume)

### The manifest (`downward-api-2.yaml`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: downwardapi-volume
  labels:
    app: good-app
    owner: hr
  annotations:
    version: good-version
spec:
  volumes:
    - name: downwardapi-volume
      downwardAPI:
        items:
          - path: labels
            fieldRef:
              fieldPath: metadata.labels
          - path: annotations
            fieldRef:
              fieldPath: metadata.annotations
  containers:
    - name: busybox
      image: busybox
      command: ["sh", "-c", "cat /etc/podinfo/*; sleep 3600"]
      volumeMounts:
        - name: downwardapi-volume
          mountPath: /etc/podinfo
```

### Walking through it

| Piece | Meaning |
|---|---|
| `volumes[].downwardAPI` | The **type** — same slot where `emptyDir` went |
| `items[].path` | The **filename** created inside the mount |
| `items[].fieldRef.fieldPath` | The **value** that goes into that file |
| `path: labels` | Creates a file literally named **`labels`** |
| `metadata.labels` | Its content = **`app=good-app`** and **`owner=hr`** |
| `path: annotations` | Creates a file named **`annotations`** |
| `metadata.annotations` | Its content = **`version=good-version`** |

Two files, two metadata fields, one mount at `/etc/podinfo`.

### A troubleshooting habit (worth internalising)

> **Always start storage troubleshooting at the volume, then follow the mount.**

1. Look at `spec.volumes` — is the volume defined, and with what type?
2. Look at the container's `volumeMounts` — is it actually mounted, and where?

Or **reverse-engineer**: start from the broken container → note its `volumeMounts` name → jump to that volume in `spec.volumes`. The name always ties them together.

### Explore it

```bash
kubectl apply -f downward-api-2.yaml
kubectl get pods                       # Running

kubectl exec -it downwardapi-volume -- sh
```

```sh
cd /etc/podinfo
ls -l
# annotations  labels        ← two entries, and they are SYMLINKS
cat annotations
cat labels
```

**`labels` contains:**

```
app="good-app"
owner="hr"
```

**`annotations` contains** your annotation **plus extra ones Kubernetes added**:

```
version="good-version"
kubectl.kubernetes.io/last-applied-configuration="..."
...
```

> That's the point made in the lecture: *"Kubernetes also adds certain annotations which we will see once we implement this YAML."* Those `kubectl.kubernetes.io/...` entries are metadata Kubernetes itself manages.

### Why symlinks?

The downwardAPI volume is refreshed **atomically**: files are written to a new timestamped directory (`.data`), and the `labels` / `annotations` symlinks are repointed. That is how injected metadata can update **without** rewriting the file in place — and it's why `ls -l` shows links.

### Read it from logs instead

Because the container's command is `cat /etc/podinfo/*`:

```bash
kubectl logs downwardapi-volume
```

Same content, no exec needed. **Two ways to see the same injected data.**

---

## 10) Preview — ConfigMaps & Secrets

Not detailed here (next-to-next lecture), but flagged as **critical**:

> **ConfigMaps and Secrets inject configuration and sensitive data into pods.**
> - **ConfigMap** → configuration
> - **Secret** → sensitive data (certificates, passwords, tokens)

### The purpose: decouple configuration from code

Same theme as every lecture since Day 01:

- **Day 11** — microservices: each tier holds **only its own logic**. Authentication, authorization, API communication, logging, caching should **not** be baked into the app.
- **Day 12** — the frontend Deployment talks to the backend Deployment through a **Service**. So do you **hardcode the backend Service URL** into your application logic?

**No** — because that name changes across deployments and environments. Instead:

> *"If you want to reach the backend, look at **this file**."*

And that file is **injected into the container by a ConfigMap**. Likewise, Secrets inject certificates and other sensitive data.

**Container image = application code only.** Everything environmental gets injected.

> Why it matters: *"extremely important, not just for your exam but also for your interviews and production implementations, because they are used all the time."*

---

## 11) Why This Topic Is Worth Extra Attention — CKA Weightage

From the official **CKA curriculum**:

> **Storage carries ~10% of the exam weightage.**

Everything in Days 24–27 (Docker volumes → ephemeral → persistent → PV/PVC/StorageClass) sits in that 10%. It's a small slice of the syllabus but a reliable source of easy points — and the concepts build on each other, so gaps compound.

---

## 12) Key Takeaways

1. **Ephemeral = gone when the pod is terminated.** Lifetime is the **pod's**, not the container's.
2. **`emptyDir` lives and dies with the pod** — deleted the instant the pod is deleted.
3. **Its reason to exist is sharing data between containers of the same pod** — mount it into several containers and they see the same bytes.
4. **Sharing across pods is impossible.** A Deployment's 5 replicas get **5 separate** `emptyDir` volumes, even on the same node.
5. **Containers keep their own writable layers** regardless — `emptyDir` is *additional* shared space, not a replacement.
6. **`emptyDir` uses host (node) storage** — on macOS/Windows the "host" is Docker Desktop's **Linux VM**, which itself sits on your base storage.
7. **YAML foundation:** the volume goes in **`spec.volumes`** (pod level) and is mounted per container in **`volumeMounts`**. *This pattern is 60% of Kubernetes storage and never changes* — only the type key does.
8. **`emptyDir: {}` = all defaults** — node disk, unlimited size. `medium: Memory` → RAM/tmpfs. `sizeLimit` caps it.
9. **`volumeMounts` is a list** — one entry per volume per container.
10. **Use cases:** scratch space, caching (fast local disk / RAM), temporary persistence of logs/files.
11. **The downwardAPI exposes pod metadata to itself:** name, namespace, labels, annotations, resource limits.
12. **Two mechanisms:** environment variables (`valueFrom.fieldRef.fieldPath`) and **files via a `downwardAPI` volume with `items`**.
13. **It exists for sidecars:** monitoring and logging helpers need pod identity to make their data meaningful.
14. **It offloads the API server** — no HTTP calls, no auth/authz per container.
15. **Kubernetes injects its own annotations** (`kubectl.kubernetes.io/last-applied-configuration`, etc.) — you'll see more than you wrote.
16. **downwardAPI files are symlinks** into a `.data` directory — that's how they refresh atomically.
17. **ConfigMaps/Secrets inject configuration**, decoupling it from the image — the same decoupling theme as Days 01/11/12.
18. **Storage is ~10% of the CKA exam.**

---

## 13) Essential Snippets

```yaml
# --- emptyDir: node disk (defaults) ---
spec:
  volumes:
    - name: temp-storage
      emptyDir: {}
  containers:
    - name: app
      volumeMounts:
        - name: temp-storage
          mountPath: /data

# --- emptyDir: RAM-backed, capped ---
  volumes:
    - name: cache
      emptyDir:
        medium: Memory
        sizeLimit: 500Mi

# --- Same volume shared by two containers ---
  containers:
    - name: busybox
      volumeMounts:
        - name: temp-storage
          mountPath: /data
    - name: busybox-2
      volumeMounts:
        - name: temp-storage       # same name = same volume
          mountPath: /data

# --- downwardAPI via env vars ---
      env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace

# --- downwardAPI via files ---
  volumes:
    - name: downwardapi-volume
      downwardAPI:
        items:
          - path: labels
            fieldRef:
              fieldPath: metadata.labels
          - path: annotations
            fieldRef:
              fieldPath: metadata.annotations
```

```bash
# Apply & verify
kubectl apply -f emptydir.yaml
kubectl get pods
kubectl get pod <pod> -o yaml           # see volumes + autofilled namespace

# Exec into a specific container (required in multi-container pods)
kubectl exec -it <pod> -c <container> -- sh

# Prove sharing
#   container 1: echo "this is my file" > /data/my-file.txt
#   container 2: cat /data/my-file.txt

# downwardAPI output
kubectl logs downwardapi-example        # env vars
kubectl logs downwardapi-volume         # file contents (cat /etc/podinfo/*)

# Docs (exam-friendly)
#   kubernetes.io/docs → search "volumes" → sidebar → emptyDir / downwardAPI
```

---

## 14) Quick Self-Check

1. Define ephemeral storage in one sentence. What is the lifetime tied to?
2. What does `emptyDir` actually add, given pods were already ephemeral?
3. Can an `emptyDir` be shared between two pods? Why not?
4. A Deployment has 5 replicas on 3 nodes. How many `emptyDir` volumes exist?
5. Which part of the YAML gives the volume to the pod, and which part mounts it into a container?
6. What does `emptyDir: {}` mean, and what are the two defaults it implies?
7. How do you make an `emptyDir` RAM-backed? What's the Docker equivalent?
8. Your pod has 3 containers; you mount `emptyDir` into only 2. Can the third read the data?
9. Why does `emptyDir` use "host storage" mean something different on macOS vs Ubuntu?
10. Name the three `emptyDir` use cases and why caching fits so well.
11. What is the downwardAPI for? Name four pieces of metadata it can expose.
12. Why would a monitoring sidecar need the pod's namespace?
13. How does the downwardAPI "offload the API server"?
14. Show the YAML fragment that injects `metadata.name` as an env var.
15. In a downwardAPI volume, what do `items[].path` and `fieldRef.fieldPath` each control?
16. Why do `labels` and `annotations` appear as symlinks inside `/etc/podinfo`?
17. Where did the extra `kubectl.kubernetes.io/...` annotations come from?
18. Which object injects configuration, and which injects sensitive data?
19. How much of the CKA exam is storage?

---

## What's Next (Day 27)

- **Persistent storage** — **PVs**, **PVCs**, and **StorageClasses**, plus the access modes and reclaim policies that come with them.

---

*End of Day 26 notes.*
