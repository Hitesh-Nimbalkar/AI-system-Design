# Multi-Container Pods — Init, Sidecar, Ambassador & Adapter — Complete Notes (Day 21)

> Source: Day 21 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Multi-container pod patterns — why we use them, and the four patterns you meet in production.
> Prerequisite: Day 07 (pod internals, namespaces, sandbox) and Day 20 (HPA/VPA, Prometheus adapter).

---

## 1) The Progression: Why Multi-Container Pods?

The course diagram walks through three stages:

| Stage | What you have | Where you saw it |
|---|---|---|
| **1** | A single container | Docker days — one container, one process |
| **2** | A pod with one container | Every manifest so far — usually `nginx` |
| **3** | A pod with **multiple** containers | Today's topic — the production patterns |

A pod *can* hold multiple containers. Today we zoom into **how** those containers are used together.

### The two things containers in a pod share

1. **Network namespace** (and therefore the IP, ports, routing tables)
2. **Storage** — but only the volumes you actually mount into each container

These two facts explain every pattern in this lecture.

---

## 2) Shared Networking (Network Namespace)

### The key idea

- A **network namespace** is a **Linux** concept — it was not invented for Kubernetes.
- When a pod is created, Kubernetes creates **one network namespace for the pod**.
- Every container in that pod **joins that same namespace**.

### What lives inside the namespace

- The pod's **IP address**
- **Ports**
- **Routing tables**
- The network interfaces (veth pair, loopback)

### Consequence 1 — `localhost` works between containers

If container 2 wants to reach nginx in container 1:

```bash
curl http://localhost:80
```

No service, no pod IP, no DNS — just `localhost`, because they are in the same namespace.

### Consequence 2 — ports are exclusive across the whole pod

- If container 1 listens on port **80**, **no other container in the pod can listen on 80**.
- Ports are part of the shared namespace, so a collision is a real conflict.

> Mental model: containers in a pod are like **processes on the same machine** — same IP, same port table, same `localhost`.

---

## 3) Shared Storage (the caveat)

Storage in Kubernetes is **defined at the pod level** and then **mounted per container**.

- Define the volume under `spec.volumes`.
- Add a `volumeMounts` entry to each container that should see it.
- A container that has **no** `volumeMounts` entry for that volume simply **cannot see it**.

### You can differ the permissions per container

Example from the lecture — nginx + log collector sharing one volume:

| Container | Role | Access to volume |
|---|---|---|
| `nginx` (main) | Writes logs | **read + write** |
| `log-collector` (helper) | Ships logs away | **read only** |

This is legitimate and common: one container writes, another container reads. Flexibilities:

- One container full rights, another minimal rights.
- All containers identical rights.
- Any permutation you can justify.

> The volume is pod-scoped, but **access is container-scoped**. That is the caveat.

---

## 4) Main Container vs Helper Container

These terms appear for the first time in the course. They are **not** Kubernetes fields — they are roles.

### Main (primary) container

- Runs the **application logic** — the actual business app.
- In the examples: `nginx`, or a `wishlist` microservice.

### Helper container

- **Supports** the main container without being the application itself.
- Collects logs, exposes metrics, proxies external calls, transforms data, etc.
- Defined in the **same `containers` list** (except init containers — see below).

### Why: decoupling

The core logic of the app should stay core. Cross-cutting concerns should not be baked in:

- authentication / authorization
- log collection and shipping
- monitoring / metrics export
- external connectivity, retries, SSL

**Decoupling** = move each of those into its own container, so the main container does only application work.

### The big payoff

If a helper container **fails**, the application **keeps running**:

- Logging container dies → you lose logs for a while, app is fine.
- Monitoring container dies → monitoring is blind, app is fine.

That is *the* reason to separate concerns instead of stuffing everything into one container.

---

## 5) The Four Patterns — and the One Structural Difference

```
                    ┌─────────────────────────────┐
                    │  Pod                        │
                    │  ┌───────────┐ ┌──────────┐ │
                    │  │ main app  │ │ helper   │ │
                    │  └───────────┘ └──────────┘ │
                    └─────────────────────────────┘
```

| Pattern | Defined in manifest as | Lifetime |
|---|---|---|
| **Init** | `spec.initContainers` — a **separate block** | Runs once, **must complete**, then disappears |
| **Sidecar** | `spec.containers` entry | Runs **alongside** the main container for the pod's life |
| **Ambassador** | `spec.containers` entry | Runs alongside — proxies **external** traffic |
| **Adapter** | `spec.containers` entry | Runs alongside — **transforms** data |

### Critical distinction (highlighted in pink vs orange on the slide)

- **Init containers** have their **own YAML block**: `initContainers:`.
- **Sidecar / Ambassador / Adapter** have **no special block**. You never write `sidecar:` or `adapter:` in YAML. They are **logical patterns** — the helper container is just another entry in `containers:` that happens to follow that pattern.

### Lifecycle distinction

- Init → completes its job, **goes away**, consumes **zero** CPU/memory afterwards.
- The other three → **stay running** with the pod and **keep consuming resources**.
  - Therefore: **always set `requests` and `limits` on helper containers** too.

---

## 6) Init Containers

### Definition

Containers that **run to completion before** any main container starts.

- They either **succeed** or **fail** — they do not "keep running".
- If an init container **fails**, the **main container never starts**. Initialization failed → don't proceed.
- You can have **multiple** init containers.
- They run **sequentially**: init 1 → init 2 → init 3 → then main app.
- **All** of them must succeed before the app starts.

```
init-1 (done) → init-2 (done) → init-3 (done) → main app starts
```

### Use cases (from the lecture)

1. **DB readiness** — don't let the app hammer a database that isn't up yet. Common when everything is deployed at once with Terraform/Ansible.
2. **API health check** — don't start the app until a required API responds (demo 1).
3. **File / directory creation & sync** — clone a GitHub repo or build a directory tree into a **shared volume** before the app starts. The app then finds the files already there.
4. **Service availability** — don't start the app until a required `ClusterIP` Service exists (demo 2).

> These are the patterns the instructor has personally used, but they are open-ended: downloading secrets, preparing config, migrating schemas, etc.

---

### Demo 1 — Single Init Container (`init-c.yaml`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: init-demo
spec:
  initContainers:
    - name: check-api
      image: curlimages/curl:latest
      command:
        - "sh"
        - "-c"
        - |
          echo "checking API availability"
          sleep 25
          until curl -s http://kubernetes.io > /dev/null; do
            echo "waiting for API"
            sleep 5
          done
          echo "API is accessible, proceeding to main app container"
  containers:
    - name: main-app
      image: nginx:latest
      ports:
        - containerPort: 80
```

### YAML details worth remembering

**`command` is a list.** Both forms are identical:

```yaml
# Bracket style (short commands)
command: ["sh", "-c", "echo hi"]

# Block style (long commands — far more readable)
command:
  - "sh"
  - "-c"
  - |
    echo hi
```

**The `|` is a YAML multi-line block indicator.** It lets one long shell string be written across many readable lines.

### Walking through the script

| Line | Purpose |
|---|---|
| `echo "checking API availability"` | First log line you'll see |
| `sleep 25` | Artificial delay so you can *observe* the init phase |
| `until curl -s http://kubernetes.io > /dev/null; do` | Loop **until** the API answers |
| `> /dev/null` | `/dev/null` is the "black hole" — suppress noisy HTML output |
| `echo "waiting for API"; sleep 5` | Retry message + 5s backoff (never seen, because kubernetes.io is ~always up) |
| `done` | End loop |
| `echo "API is accessible, proceeding..."` | Loop exited → init container exits **0** |

`kubernetes.io` is used because it sits on highly-available infrastructure with ~99.999999999% uptime, so it practically always succeeds — the `sleep 25` is what makes the demonstration visible.

### Apply and observe

```bash
kubectl apply -f init-c.yaml
kubectl get pods
```

Watch the `READY` column carefully:

```
NAME        READY   STATUS     RESTARTS   AGE
init-demo   0/1     Init:0/1   0          5s
```

**Why `0/1` and not `0/2`?** Because `kubectl get pods` counts **only application containers** in the READY column. Init containers are not counted. So:

- Pod with 1 app container + 1 init container → **`0/1` → `1/1`**
- Pod with 2 app containers → **`0/2` → `2/2`**
- Init phase statuses: `Init:0/1`, `Init:1/1` (second init done), `PodInitializing`

### Checking init container logs

You must name the container, because the pod has more than one:

```bash
kubectl logs init-demo -c check-api
```

Output (after 25 s):

```
checking API availability
API is accessible, proceeding to main app container
```

Then:

```bash
kubectl get pods
# init-demo   1/1   Running   0   40s
```

The single `1/1` is the **main** container — it only started once the init container completed.

### Watching it again (with force delete)

```bash
kubectl delete pod init-demo --force
kubectl apply -f init-c.yaml
kubectl get pods
kubectl logs init-demo -c check-api
kubectl logs init-demo -c main-app      # nginx startup logs, once running
```

`--force` skips the graceful shutdown request — handy when you don't want to wait for termination.

---

### Demo 2 — Multiple Init Containers (`init-2.yaml`)

Same pod, but two init containers running **in sequence**.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: init-demo-2
spec:
  initContainers:
    - name: check-api
      image: curlimages/curl:latest
      command:
        - "sh"
        - "-c"
        - |
          echo "checking external API availability"
          sleep 15
          until curl -s http://kubernetes.io > /dev/null; do
            echo "waiting for external API"
            sleep 5
          done
          echo "external API accessible, proceeding to next init container"

    - name: check-svc
      image: busybox:latest
      command:
        - "sh"
        - "-c"
        - |
          echo "checking main app service availability"
          until nslookup main-app-svc.default.svc.cluster.local; do
            echo "waiting for service DNS resolution"
            sleep 5
          done
          echo "service is reachable, proceeding to main app container"

  containers:
    - name: main-app
      image: nginx:latest
      ports:
        - containerPort: 80
```

### What the second init container enforces

- It looks up `main-app-svc.default.svc.cluster.local` **every 5 seconds**.
- If that Service does not exist, the init container **never succeeds** → the pod sits at `Init:1/2` **forever** → the main container never starts.

```bash
kubectl apply -f init-2.yaml
kubectl get pods
# init-demo-2   0/1   Init:0/2   ...

kubectl logs init-demo-2 -c check-svc
# checking main app service availability
# waiting for service DNS resolution
# waiting for service DNS resolution
```

### Creating the missing Service (`svc.yaml`)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: main-app-svc
spec:
  type: ClusterIP
  selector:
    app: main-app
  ports:
    - port: 80
      targetPort: 80
```

```bash
kubectl apply -f svc.yaml
kubectl logs init-demo-2 -c check-svc
```

Within one retry cycle (≤ 5 s):

```
service is reachable, proceeding to main app container
```

It also prints the **resolved IP** the Service was assigned (e.g. `10.96.135.170`). Then the pod flips to `2/2`, init containers vanish, and only nginx remains.

> **The rule:** *all* init containers must succeed before *any* main container starts.

---

### Sidebar — Where does that DNS name come from?

```bash
kubectl get svc -n kube-system
```

Shows the **`kube-dns`** Service with IP **`10.96.0.10`**.

```bash
kubectl get pods -n kube-system
```

Shows **two CoreDNS pods**; the `kube-dns` Service load-balances DNS queries across them.

Every DNS lookup in the cluster (including `nslookup main-app-svc...`) is answered by CoreDNS through that Service IP. Full treatment comes in the DNS section of the course; just remember **`10.96.0.10` = the cluster DNS entry point**.

### Troubleshooting lesson from the demo

The second pull failed with `ErrImagePull` / `ImagePullBackOff`, then `kubectl describe pod` showed:

```
failed to pull and unpack image ... server misbehaving
```

The cause was **the instructor's internet connection**, not the YAML — the same image had worked minutes earlier. Reading the manifest again would not have helped; `kubectl describe pod` (bottom **Events** section) is what points at image-pull failures.

**Debug flow for a stuck pod:**

```bash
kubectl get pods
kubectl describe pod <pod>        # check Events + container states
kubectl logs <pod> -c <container>
```

---

## 7) Sidecar Pattern

### Definition

A helper container that **extends or complements** the functionality of the main container. It runs **alongside** it for the pod's whole life. **The most common pattern in production.**

### Use cases

1. **Logging** — read/ship the main container's log files from a shared volume to a central repository (S3, Elasticsearch). Tooling: **Fluentd**, **Fluent Bit**.
2. **Monitoring** — export metrics for the app; a **Prometheus** exporter alongside the app does exactly this.
3. **Proxy / service mesh** — this is where the term *proxy* earns its own definition.
4. **Data synchronization** — continuously sync files in/out of a shared volume.

### What is a proxy (general definition)

> A proxy is someone doing **your** job **in your place**, often because you don't want to reveal your identity.

Not a Kubernetes word — a general networking word. In Kubernetes, the classic proxy example is a **service mesh**.

### Service mesh — why sidecars

A **service mesh** is an **infrastructure layer that manages communication between microservices**. You see it in larger implementations with many services.

What it gives you:

| Capability | Detail |
|---|---|
| **Traffic management** | routing, load balancing, **traffic shaping** (e.g. cap A→B at 50 Mbps) |
| **Security** | **mTLS** (mutual TLS) between services, authentication, authorization |
| **Observability** | telemetry, **distributed tracing**, logging |

Examples: **Istio**, **AWS App Mesh**.

These meshes are deployed **as sidecar containers** — one proxy container per pod, transparently intercepting traffic. (The alternative, a per-node proxy, is the "sidecar-less"/ambient model — not covered here.)

### The init vs sidecar difference, in one line

- **Init** does its job, succeeds, and **disappears** — so *one-time* setup only.
- **Sidecar** keeps running — so it can do *continuous* work (stream logs, sync data, keep proxying).

This is why continuous **data synchronization** belongs to sidecar, not init: init clones once and is gone; sidecar keeps syncing.

### Failure behaviour

Sidecars can fail — but the **main container keeps working**. A dead log sidecar means missing logs, not a broken app. A dead metrics sidecar means a monitoring gap, not an outage. That isolation is the entire point of decoupling.

---

### Demo 3 — Sidecar (`sidecar.yaml`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sidecar-logging-demo
spec:
  restartPolicy: Always          # default — see the experiment below
  containers:
    - name: main-app
      image: nginx:latest
      ports:
        - containerPort: 80

    - name: health-logger
      image: curlimages/curl:latest
      command:
        - "sh"
        - "-c"
        - |
          while true; do
            curl -s http://localhost:80 > /dev/null && echo "main app is healthy" || echo "main app is unhealthy"
            sleep 5
          done
```

### Why `localhost:80` works from the helper

Because both containers **share the pod's network namespace**. Same IP, same port table.

### Shell operators used

| Operator | Meaning |
|---|---|
| `&&` | run the next command **only if** the previous **succeeded** |
| `\|\|` | run the next command **only if** the previous **failed** |
| `while true; do ... done` | infinite loop |
| `curl -s ... > /dev/null` | silent probe, output discarded |

So the helper prints `main app is healthy` while nginx answers, and `main app is unhealthy` the moment it doesn't.

### Apply

```bash
kubectl apply -f sidecar.yaml
kubectl get pods
# sidecar-logging-demo   2/2   Running   0   20s
```

**`2/2` — both containers are application containers.** Sidecar/ambassador/adapter containers *are counted* here; init containers never are.

```bash
kubectl logs sidecar-logging-demo -c health-logger
# main app is healthy
# main app is healthy
# main app is healthy
```

### Killing the main container — the `restartPolicy` lesson

Enter the main container:

```bash
kubectl exec -it sidecar-logging-demo -c main-app -- /bin/sh
```

Inside it:

```sh
kill 1
```

You are thrown out — you killed the container's PID 1.

```bash
kubectl get pods
# sidecar-logging-demo   2/2   Running   1   2m
```

**The container came back.** `RESTARTS: 1`.

Why? The **kubelet** always restarts containers that fail, according to the pod's **`restartPolicy`**. The default (and the value on any pod you create without specifying it) is:

```yaml
restartPolicy: Always
```

Verify it yourself:

```bash
kubectl get pod sidecar-logging-demo -o yaml
```

Scroll to `spec.restartPolicy` → `Always`.

#### The experiment: `restartPolicy: Never`

Edit the manifest, add under `spec`:

```yaml
spec:
  restartPolicy: Never
  containers:
    ...
```

```bash
kubectl delete pod sidecar-logging-demo --force
kubectl apply -f sidecar.yaml
kubectl get pods -w          # -w = watch, prints status changes live
```

Once `2/2` is ready, exec in and `kill 1` again. Result:

```bash
kubectl get pods
# sidecar-logging-demo   1/2   NotReady   1   2m
```

- The main container is **gone** and **not restarted**.
- Only **one of two** containers is ready → pod is `1/2`.
- The sidecar is still running (and will keep reporting).

```bash
kubectl logs sidecar-logging-demo -c health-logger
# main app is unhealthy
# main app is unhealthy
```

The sidecar immediately detects the dead main container, because it probes `localhost:80`.

> **Exam-relevant:** `restartPolicy` values are `Always` (default), `OnFailure`, `Never`. It is set at the **pod** level and cannot be changed after creation — you must recreate the pod. `Always` is mandatory for pods owned by a Deployment/ReplicaSet.

---

## 8) Ambassador Pattern

### Definition

A container that acts as a **proxy / intermediary between the main application and an external system**.

**"External system" is the keyword.** Anything **outside** the Kubernetes cluster belongs to the ambassador's job:

- Amazon **SQS / SNS**
- Azure **API Gateway**
- An external database or third-party API

### Why not let the app do it?

Same argument as before — **decoupling**:

- The application should only do application work.
- Authentication, authorization, connection pooling, retries, TLS **do not belong in business logic**.

> In the lecture's example: the `wishlist` microservice should handle wishlists and nothing else.

The ambassador **centralizes all logic required for external communication**, so the main container only sees a clean local endpoint.

### Use cases

| Use case | What the ambassador handles |
|---|---|
| **API gateway / request routing** | Single local entry point for external calls. **Envoy** is a common implementation. |
| **Connection management** | Open/close/pool database or API connections. App asks 10×/min; connections are reused instead of re-established (saves CPU, memory, and code complexity). |
| **Retries** | External API unreachable → the helper retries with backoff. The app never writes retry code. |
| **SSL termination** | TLS handshake/termination handled by the helper; the app speaks plain HTTP locally. |

### Shape of it

```
main container ──> localhost:PORT (ambassador) ──> external service (SQS / API / DB)
```

Sketch of the container entry (illustrative — the lecture did not demo ambassador):

```yaml
    - name: ambassador
      image: envoyproxy/envoy:distroless-v1.31-latest
      ports:
        - containerPort: 9901
```

Nothing special in the manifest — it's a normal entry in `containers:`.

---

## 9) Adapter Pattern

### Definition

A container that **transforms or normalizes data** between the main application and an external system.

**The simplest of the four to describe:** it sits in the middle and **rewrites the format**.

### Use case 1 — Metric transformation (you already saw this on Day 20)

- **Prometheus Adapter** converts **Prometheus metrics** into the **Kubernetes API format** (`custom.metrics.k8s.io` / `external.metrics.k8s.io`).
- If the Prometheus Adapter ran as a container **inside** the Prometheus server's pod, that deployment would literally be the **adapter pattern**.

That is why the word "adapter" felt familiar — Day 20 introduced it as a component; today it's named as a pattern.

### Use case 2 — Log normalization

| Producer | Consumer | Adapter's job |
|---|---|---|
| Logs in **JSON** | Destination that supports only **YAML** (or a fixed schema) | Convert JSON → the required format |

The adapter can also enrich, flatten, or reshape fields before shipping.

---

## 10) Pattern Comparison — One Table

| | **Init** | **Sidecar** | **Ambassador** | **Adapter** |
|---|---|---|---|---|
| **YAML location** | `spec.initContainers` | `spec.containers` | `spec.containers` | `spec.containers` |
| **Is it a K8s field?** | **Yes** — a real distinct block | No — a **logical pattern** | No — logical pattern | No — logical pattern |
| **Lifetime** | Runs to completion, then gone | Runs with the pod | Runs with the pod | Runs with the pod |
| **Ordering** | Sequential, before app | Parallel with app | Parallel with app | Parallel with app |
| **Can block app start?** | **Yes** — all must succeed | No | No | No |
| **Consumes resources after startup?** | **No** | Yes | Yes | Yes |
| **Failure impact on app** | App never starts | App keeps running | App keeps running (external calls fail) | App keeps running |
| **Direction** | Setup | Local / outbound observability | **Outbound to external world** | **Format translation** |
| **Typical use** | DB ready, API ready, clone repo, wait for Service | Log shipping, metrics, service mesh proxy, data sync | API gateway, connection pooling, retries, SSL | Prometheus adapter, log normalization |
| **Counted in `READY`?** | **No** | Yes | Yes | Yes |

---

## 11) How the Manifests Differ (the visual point of the slide)

### Init container — separate block

```yaml
spec:
  initContainers:            # ← its own key, a LIST for sequencing
    - name: prepare-environment
      image: busybox
      command: ["sh", "-c", "echo preparing the environment; sleep 10"]
  containers:
    - name: main-app
      image: nginx
```

The lecture's placeholder init container just slept 10 seconds ("preparing the environment"); in production it does real work.

### Sidecar / ambassador / adapter — inside `containers`

```yaml
spec:
  containers:
    - name: main-app          # main
      image: nginx
    - name: helper-1          # sidecar / ambassador / adapter
      image: curlimages/curl
    - name: helper-2          # another helper
      image: envoyproxy/envoy
```

No `sidecar:` key exists. If someone asks "where do you define a sidecar container?" the answer is **"in the containers list — the pattern is conceptual, not declarative."**

### Why `initContainers` is plural and a list

Because you can (and often do) have several, and **order matters** — they run in the order written.

---

## 12) Best Practices & Gotchas

1. **Set `requests` and `limits` on every helper container.** Long-lived helpers consume real CPU/memory for the pod's whole life (Day 19).
   - Init containers are exempt in practice — they're gone before steady state.
2. **`README`-level truth:** the patterns are **logical abstractions**. Two engineers can look at the same 3-container pod and disagree on whether container 3 is a sidecar or an ambassador. Judge by **what it talks to**.
3. **Don't over-engineer.** Multi-container adds complexity, log noise, and resource overhead. Use a helper only when decoupling buys you something.
4. **Image pulls are a common failure.** `ErrImagePull` / `ImagePullBackOff` → `kubectl describe pod` → Events.
5. **Init containers cannot be "restarted" individually** — if one fails, the kubelet **re-runs the whole init sequence** from the failed one.
6. **`restartPolicy` is immutable per pod.** Changing it requires recreating the pod.
7. **Port collisions are real** — shared namespace means one listener per port for the entire pod.
8. **Real-world variants** beyond the lecture: a sidecar rotating certificates, an init container fetching secrets, a sidecar acting as a config reloader. The four names are the vocabulary, not the limit.

---

## 13) Demo Cheat Sheet (commands actually run)

```bash
# --- Init containers ---
kubectl apply -f init-c.yaml
kubectl get pods                       # 0/1  Init:0/1
kubectl logs init-demo -c check-api
kubectl get pods                       # 1/1  Running
kubectl delete pod init-demo --force

# --- Multiple init containers ---
kubectl apply -f init-2.yaml
kubectl get pods                       # 0/1  Init:0/2
kubectl logs init-demo-2 -c check-api
kubectl logs init-demo-2 -c check-svc  # stuck: waiting for service
kubectl apply -f svc.yaml              # create main-app-svc
kubectl logs init-demo-2 -c check-svc  # service is reachable
kubectl get pods                       # 1/1  Running

# --- Cluster DNS ---
kubectl get svc -n kube-system         # kube-dns → 10.96.0.10
kubectl get pods -n kube-system        # 2 × coredns

# --- Sidecar ---
kubectl apply -f sidecar.yaml
kubectl get pods                       # 2/2  Running
kubectl logs sidecar-logging-demo -c health-logger
kubectl exec -it sidecar-logging-demo -c main-app -- /bin/sh
#   inside: kill 1
kubectl get pods                       # 2/2  Running  RESTARTS 1  (restartPolicy Always)
kubectl get pod sidecar-logging-demo -o yaml | Select-String restartPolicy

# switch manifest to restartPolicy: Never, then:
kubectl delete pod sidecar-logging-demo --force
kubectl apply -f sidecar.yaml
kubectl get pods -w
#   exec in, kill 1
kubectl get pods                       # 1/2  NotReady  (no restart)
kubectl logs sidecar-logging-demo -c health-logger   # main app is unhealthy
```

---

## 14) Key Takeaways

1. **A pod shares its network namespace and its pod-scoped volumes** — that is what makes multi-container pods possible. Containers reach each other on `localhost`; one port, one listener.
2. **Storage is pod-scoped but mounted per container** — a container without a `volumeMount` cannot see the volume; permissions can differ per container (read-write vs read-only).
3. **Main container = application logic. Helper container = everything else.** Decoupling auth, logging, monitoring, and external I/O keeps the app simple and failure-isolated.
4. **A failed helper does not take down the app.** A failed init container *does* prevent the app from starting.
5. **Only `initContainers` gets its own YAML block.** Sidecar, ambassador, adapter are **patterns** expressed as extra entries in `containers:`.
6. **Init containers: run to completion, sequential, all must succeed, then they vanish** (no ongoing resource cost).
7. **Init use cases:** DB readiness, API health check, file/dir sync (git clone), Service availability.
8. **Sidecar use cases:** logging (Fluentd/Fluent Bit), monitoring (Prometheus), proxy/service mesh (**Istio**, **AWS App Mesh**: traffic shaping, mTLS, distributed tracing), continuous data sync.
9. **Ambassador = proxy to the outside world:** API gateway/routing (Envoy), connection management, retries, SSL termination.
10. **Adapter = data translator:** Prometheus Adapter (metrics → K8s API format), log normalization (JSON → YAML).
11. **`kubectl get pods` READY counts app containers only** — `0/1` while init runs, `2/2` when a sidecar is present.
12. **`restartPolicy: Always` is the default** — killing PID 1 in a container makes the kubelet restart it (RESTARTS increments). `Never` proves it by leaving the pod `NotReady` at `1/2`.
13. **Always set requests/limits on long-lived helper containers.**

---

## 15) Essential Snippets

```yaml
# Init container — separate block, ordered list
spec:
  initContainers:
    - name: check-svc
      image: busybox
      command: ["sh", "-c", "until nslookup main-app-svc.default.svc.cluster.local; do sleep 5; done"]

# Sidecar / ambassador / adapter — plain containers entries
spec:
  containers:
    - name: main-app
      image: nginx
    - name: helper
      image: curlimages/curl
      command: ["sh", "-c", "while true; do curl -s localhost:80 >/dev/null && echo healthy || echo unhealthy; sleep 5; done"]

# Restart behaviour
spec:
  restartPolicy: Always   # Always (default) | OnFailure | Never
```

```bash
# Logs from a specific container in a multi-container pod
kubectl logs <pod> -c <container>

# Shell inside a specific container
kubectl exec -it <pod> -c <container> -- /bin/sh

# Inspect restart policy / container list
kubectl get pod <pod> -o yaml

# Live status changes
kubectl get pods -w
```

---

## 16) Quick Self-Check

1. Why does `kubectl get pods` show `0/1` when a pod has one init container and one app container?
2. Two containers in a pod: can both bind port 8080? Why or why not?
3. You need a repo cloned **once** before the app starts — init or sidecar? And if the repo must stay in sync continuously?
4. Where in the YAML do you declare a sidecar container? What key do you use?
5. Which pattern does the Prometheus Adapter represent, and what exactly does it transform?
6. A helper container crashes. Does the application stop? What if an init container crashes?
7. You set `restartPolicy: Never`, kill the app container, and the pod shows `1/2`. Explain the `1` and the `2`.
8. Which resource requests must you not forget for the three long-lived patterns, and why not for init containers?

---

## What's Next (Day 22)

- **Pod troubleshooting** — termination (SIGTERM/SIGKILL, `terminationGracePeriodSeconds`), restart policies, image pull policies, pod lifecycle phases, and common errors (`ErrImagePull`, `ImagePullBackOff`, `CrashLoopBackOff`, `OOMKilled`).
- **Health probes** were postponed to Day 23 — liveness, readiness, and startup probes.

---

*End of Day 21 notes.*
