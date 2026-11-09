# Pod Troubleshooting — Termination, Restart & Image Pull Policies, Lifecycle & Errors (Day 22)

> Source: Day 22 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Pod termination (SIGTERM/SIGKILL), restart policies, image pull policies, pod lifecycle phases, and the common pod errors.
> Note: health probes were **postponed** — the instructor covered troubleshooting first because it makes probes easier to understand.
> Prerequisite: Day 07 (deployment creation workflow, control plane ↔ data plane), Day 15 (scheduling), Day 19 (requests/limits, OOMKilled), Day 21 (multi-container pods, `restartPolicy`).

---

## 1) When Does a Pod Get Terminated?

A pod is removed from the cluster for many reasons, but they all funnel into the **same termination procedure**:

| Trigger | Example |
|---|---|
| **Manual delete** | `kubectl delete pod my-pod` |
| **Scale-in** | Deployment replicas reduced |
| **Eviction by taint** | A `NoExecute` taint on the node, and the pod has **no matching toleration** (Day 16) |
| **Any other reason** | Node drain, rescheduling, rollout, etc. |

Whatever the cause, **does not matter** — the sequence below is identical.

---

## 2) The Termination Sequence (SIGTERM → SIGKILL)

```
kubectl delete pod my-pod
        │
        ▼
  SIGTERM ──► sent to ALL containers in the pod
        │
        ├── container exits within grace period ──► pod terminates cleanly
        │
        └── container still alive after 30s ──► SIGKILL ──► force killed
```

### Step by step

1. You run `kubectl delete pod my-pod`.
2. **SIGTERM** is sent to **every container** in that pod (not just one).
3. Containers get **30 seconds by default** to shut down gracefully.
4. If a container is **still running after 30 s**, a **SIGKILL** is sent — immediate, uncatchable termination.
5. Once all containers are down, the pod object is removed.

### How containers actually handle SIGTERM

- All major programming languages ship an **event handler** (also called a **signal handler**).
- The handler is what makes a container react to SIGTERM — close DB connections, flush buffers, finish in-flight requests.
- If the signal handler is present and works, the container exits cleanly and the pod terminates gracefully.

### Two ways graceful shutdown fails

| Failure mode | What happens |
|---|---|
| **Handler is broken/modified** so it can't handle SIGTERM | Container never exits on its own → **SIGKILL** at the 30 s mark |
| **Handler works, but shutdown takes > 30 s** | Grace period expires → **SIGKILL** |

Either way, the pod still terminates — just **not gracefully**.

### The grace period is configurable

```yaml
spec:
  terminationGracePeriodSeconds: 40   # default is 30
  containers:
    - name: app
      image: nginx
    - name: helper
      image: busybox
```

- If your app genuinely needs **35 seconds** to drain, set **40** — not 30.
- `terminationGracePeriodSeconds` is **pod-level**, so it applies to **all** containers in the pod. Both containers above get 40 s.

> Rule of thumb: `terminationGracePeriodSeconds` should be **slightly larger** than your slowest container's real shutdown time.

---

## 3) Force Deletion — `--force` and `--grace-period=0`

Normal deletion waits for the grace period. Two flags change that.

### `--force=true`

```bash
kubectl delete pod my-pod --force=true
```

- The **pod object is deleted immediately** from the API server (and therefore from etcd).
- `kubectl get pods` **no longer shows the pod** — the CLI talks to the API server, and the API server has no record of it.
- **But** the **kubelet on the node keeps monitoring those containers** — it still knows about the containers and will finish cleaning them up. The object is gone; the processes may not be.

### `--force=true --grace-period=0`

```bash
kubectl delete pod my-pod --force=true --grace-period=0
```

- You are explicitly saying: *"I don't care whether the app shuts down gracefully."*
- **No SIGTERM at all** — **SIGKILL immediately**.
- This is the "I want it gone right now" option.

### Comparison

| Command | SIGTERM sent? | Grace period | Pod visible in `get pods`? |
|---|---|---|---|
| `kubectl delete pod p` | Yes | 30 s (default) | Until termination completes |
| `kubectl delete pod p --force=true` | Yes | Grace period, but object removed at once | **No** — immediately gone |
| `kubectl delete pod p --force --grace-period=0` | **No** | **0 s** → instant SIGKILL | **No** — immediately gone |

> **Why bother?** Force delete is the escape hatch when a pod is stuck in `Terminating` (finalizers, unresponsive node, a broken handler). It's also what the instructor used repeatedly in Day 21 demos to avoid waiting.
> **Caution:** force deletion can leave orphaned containers/processes on the node and skips any cleanup logic your app had. Never use it as a routine habit on stateful workloads.

---

## 4) Restart Policies

### Scope: pod level

- `restartPolicy` is a **pod-level** field under `spec`.
- Therefore **one policy covers every container in the pod** — you cannot set it per container.

### The three values

| Policy | Restarts when… | Default for |
|---|---|---|
| **Always** | **Regardless of exit code** (0 or non-zero) | **Deployments**, **StatefulSets**, **DaemonSets**, and **manually created pods** (`kubectl run`, `kubectl apply` of a bare pod) |
| **OnFailure** | **Only** when exit code is **non-zero** | **Jobs** and **CronJobs** |
| **Never** | **Never** — not even on failure | **Nothing** — no object defaults to `Never` |

### Exit codes are the whole story

| Exit code | Meaning |
|---|---|
| **0** | **Success** — the container did its job |
| **non-zero** | **Failure** — the container errored out |

The kubelet uses this to decide, under `OnFailure`, whether to restart.

---

### Always — "keep this thing alive"

**Use case:** applications that must run forever.

- **nginx** — a web server / frontend. If it dies, you want it back **immediately**.
- Backend services, and microservices: `wishlist`, `orders`, `payments` — none of these should ever be down.
- For all of these, deployments use `Always` so the kubelet restarts a dead pod quickly.

**Behaviour:** container is restarted **regardless of its exit code** — even after a *successful* exit.

That last part is the catch. If you run a pod whose job is to `ping 4.4.4.4` and exit, and the policy is `Always`, the container **succeeds… and gets restarted anyway**, forever. Which is exactly what produces `CrashLoopBackOff` in the Day 22 demo.

> If you're running a one-shot job as a Deployment (which you shouldn't), you'd need to override the policy to `OnFailure` or `Never`.

### OnFailure — "retry until it works"

**Use case:** tasks that should run **once and succeed**.

- `ping 4.4.4.4`: succeeded → **don't restart**. Failed → **restart until it succeeds**.
- Common in **Jobs**, **CronJobs**, and **batch processing**.
- One-off copy tasks: copy a file from A to B; once done, the pod should not keep consuming resources. Let it sit `Completed`, and let a CronJob/automation clean it up.

**Behaviour:** restarted **only if it exits non-zero**.

- The kubelet only restarts pods governed by `OnFailure` **if that pod has actually failed** — and "failed" means **non-zero exit code**.
- A data-processing job that errors → restarted. A job that finishes with exit 0 → not restarted.

### Never — "leave it exactly as it is"

**Use case:** you want to **inspect the result**, including failures.

- A job that keeps failing: set `Never`, let it fail **once**, then read `kubectl logs` and fix the bug.
- One-off **diagnostic pods** — you want to see the outcome of a container execution without a restart covering it up.
- Any corner case where a restart is actively undesirable.

**Behaviour:** **not restarted even on failure.**

> `Never` is the default for **nothing**. You always opt into it.

---

### Pod-level vs controller-level (the slide)

| YAML | Policy shown |
|---|---|
| Bare **Pod** (spec section, right under `spec`) | `restartPolicy: Always` |
| **Job** | `restartPolicy: OnFailure` |
| **Diagnostic pod** | `restartPolicy: Never` |

```yaml
# Bare pod — default Always
spec:
  restartPolicy: Always
  containers:
    - name: app
      image: nginx

# Job — default OnFailure
apiVersion: batch/v1
kind: Job
metadata:
  name: ping-check
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: ping
          image: busybox
          command: ["sh", "-c", "ping -c 3 4.4.4.4"]

# Diagnostic pod — opt in to Never
spec:
  restartPolicy: Never
  containers:
    - name: diag
      image: busybox
      command: ["sh", "-c", "nslookup my-svc"]
```

> **Immutability reminder (from Day 21):** `restartPolicy` cannot be patched on a running pod. Change the manifest and **recreate** the pod.

---

## 5) Image Pull Policies

### Scope: container level (unlike restart policy)

- `imagePullPolicy` lives **inside each container**.
- In theory every container in a pod could use a different policy. In practice you won't — but you *could*.

### Definition

> **When should the container runtime pull the image from the registry?**

Should it pull even when a copy is cached on the node? Should it never pull? The policy answers that.

### The three values

| Value | Behaviour | Use case |
|---|---|---|
| **Always** | Pulls the image **every time the container starts**, even if cached | **Development** — always want the newest image |
| **IfNotPresent** | Uses the **node's cache**; pulls **only if absent** | **Production** — avoid needless pulls |
| **Never** | **Never pulls**; image must already exist on the node | **Air-gapped** environments, preloaded nodes |

---

### Always — development

- In dev you often use the **`latest`** tag — and if you supply **no tag at all**, Kubernetes appends `latest` automatically.
- Today `latest` might resolve to `my-first-image:v1`; tomorrow `1.0.1`; the day after `1.0.2`. The number keeps climbing.
- In dev you **don't care** which version — you just want the newest. So `Always`.

**Behaviour:** image pulled every time the container starts, guaranteeing the most recent image.

**Never use `Always` in production** — your developers keep improving, so `Always` would silently pull a **different version** on every restart. Production must be deterministic.

### IfNotPresent — production

- Use in production **to avoid unnecessary pulls**.
- Reasons to avoid pulls: **bandwidth** cost, and **node utilization** goes up while downloading.
- **Behaviour:** use the image in the node's cache; pull from the registry only if it isn't there.

### The tag-mutability trap ("Varun and Kavita" story)

This is the reason version tags are not enough on their own.

**Setup:**

- Two developers: **Varun** and **Kavita**.
- Varun pushes an image as **`v1.0.1`**.
- Kavita builds her own image and pushes it with the **same tag `v1.0.1`**. **Nothing stops her** — the registry now has two different images under one tag (the second overwrites the first in most registries).

**Two nodes:**

- **Node 1** pulled the image first → got **Varun's** `v1.0.1`.
- **Node 2** pulled later → got **Kavita's** `v1.0.1`.

**Result:** same tag, **two different codebases** running in the same cluster. You don't know what Varun changed; you *definitely* don't know what Kavita changed. Debugging becomes guesswork.

**The fix is process, not YAML:**

- Enforce at the **build/push pipeline** that a tag **cannot be overwritten** — reject the push if the tag already exists.
- Don't rely on "please don't reuse tags" — put **automation** in place that prohibits it.
- Immutable tags (or digest pinning, `image@sha256:...`) remove the ambiguity entirely.

> `IfNotPresent` is **tricky if your tagging discipline is weak**. Same tag ≠ same image across nodes.

### Never — air-gapped

*"If we never pull the image, how do we run containers?"*

- Nodes must be **preloaded** with the images (`docker load` / `ctr images import`, or a build-time bake).
- **Air-gapped environments** = tightly governed environments where servers are **isolated from the external network** and have **no internet access**. External image pulls are not allowed at all.
- **Behaviour:** if the image isn't present locally, **the pod fails to start**. Obvious — and intended.

### Why the Day 21 demos kept pulling images

The instructor's internet dropped and every pull failed. Root cause: **the pull policy was `Always`**.

Why? The manifests used `nginx:latest` (or no tag). **With `latest` or no tag, the default policy is `Always`** — so Kubernetes tried to pull on every start, even with an identical image cached.

### Default policies (dependent on how you write the image)

| Image in the manifest | Default `imagePullPolicy` |
|---|---|
| `nginx:latest` — or `nginx` with **no tag** | **`Always`** |
| `nginx:1.2.3` — any **version tag** | **`IfNotPresent`** |
| Explicit `imagePullPolicy` set | Whatever you set |

> **Production rule:** always use **version-tagged** images (`myapp:1.2.3`), which conveniently also gives you the safer `IfNotPresent` default. This is exactly what the Day 10 rolling update / rollback demo relied on.

### Semantic versioning refresher

```
myapp:1.2.3
       │ │ └── patch  → bug fixes
       │ └──── minor  → new features, backwards compatible
       └────── major  → breaking changes
```

### Private registries

Public images (`nginx` from Docker Hub) need **no credentials** — Docker Hub is the default registry Kubernetes queries.

Private registries **do** require authentication. Supply it via an **image pull secret**:

```bash
kubectl create secret docker-registry regcred \
  --docker-server=<registry> \
  --docker-username=<user> \
  --docker-password=<pass> \
  --docker-email=<email>
```

```yaml
spec:
  imagePullSecrets:
    - name: regcred
  containers:
    - name: app
      image: myregistry.example.com/myapp:1.2.3
```

Missing or wrong credentials → **`ErrImagePull`**.

---

## 6) Pod Lifecycle Phases

> The instructor's prerequisite: **watch Day 07 first** — the deployment creation workflow explains how control plane and data plane components cooperate.

### What actually happens when you create a pod

```
kubectl run my-pod --image=...
        │
        ▼
[API Server]  validates, writes the object to etcd  ──► "pod created" returned to you
        │
        ▼
[Scheduler]   sees a pod with no nodeName
              checks: resource availability, taints/tolerations,
                      affinity/anti-affinity  (Day 15)
        │
        ▼
[Scheduler]   picks a node → updates nodeName ──► API Server writes it to etcd
        │
        ▼
[Kubelet]     on that node, gets the pod spec via API Server
        │
        ▼
[Container runtime]  pulls the image
                     sets up networking via CNI
                     creates cgroups
                     mounts volumes, injects env vars
        │
        ▼
   Container running  →  Pod is Running
```

**Critical insight:** the API server confirms **"pod created"** the moment it writes the object to etcd — **before scheduling, before image pull, before anything runs**. That's why `kubectl run` with a nonsense image still prints "pod created" and only later shows `ErrImagePull`.

### The five phases

| Phase | Meaning | Typical causes |
|---|---|---|
| **Pending** | Pod accepted by the cluster, but containers **not yet running** | Not yet scheduled; image pull delays; resources unavailable; taints without tolerations |
| **Running** | Scheduled to a node; containers **running or starting** | Normal steady state |
| **Succeeded** | **All** containers terminated **successfully** (exit 0); pod **will not restart** | Completed Jobs, `restartPolicy: OnFailure`/`Never` |
| **Failed** | All containers terminated, **at least one non-zero** exit, **and not restarting** | Failed Jobs / diagnostics with `Never` |
| **Unknown** | Kubernetes **cannot determine** the state | Node communication loss, infrastructure failure |

### Pending has a sub-phase: `ContainerCreating`

You will frequently see this instead of `Pending`:

```
NAME      READY   STATUS              RESTARTS   AGE
my-pod    0/1     ContainerCreating   0          5s
```

- Image being pulled, CNI networking being set up, volumes mounting, env vars injecting.
- Stuck `ContainerCreating` → almost always an **image pull**, **volume mount**, or **CNI** problem. `kubectl describe pod` names it.

### Succeeded vs Completed — the naming gotcha

- **Phase** (API / `kubectl describe`): **`Succeeded`**
- **Visible status** (`kubectl get pods`): **`Completed`**

They mean the same thing. Docs say *Succeeded*; the CLI prints *Completed*.

### The worst-container rule (very exam-relevant)

> **Overall pod status = the status of the worst container in the pod.**

- 5 containers, 4 healthy, 1 in `ErrImagePull` → pod shows **`ErrImagePull`**, and READY shows **`4/5`**.
- A pod is only `Running` when **all** containers are running or starting.
- One broken container poisons the displayed status of the whole pod — so when a pod looks broken, **look at every container**, not just the first.

### Phase depends on restart policy

You will **only** see `Succeeded` / `Completed` and `Failed` when the pod is **not** being restarted:

| Scenario | Result |
|---|---|
| Container exits 0, `restartPolicy: Always` | **Restarts** → eventually `CrashLoopBackOff` (never `Completed`) |
| Container exits 0, `restartPolicy: OnFailure`/`Never` | Stays `Completed` / `Succeeded` |
| Container exits non-zero, `Never` | Stays `Failed` |
| Container exits non-zero, `Always`/`OnFailure` | **Restarts** → `CrashLoopBackOff` |

> **Restart policy and lifecycle phases are two sides of one coin.** You won't see `Succeeded`/`Failed` on a pod that keeps restarting.

---

## 7) Demo — Watching Phases Happen

### Setup

```bash
kubectl get pods -w        # -w = watch: reprints whenever status changes
```

The instructor split the terminal vertically: `kubectl get pods -w` on the left, commands on the right.

### Demo A — a bad image, and the pull backoff ladder

```bash
kubectl run my-pod --image=amazing-me     # nonsense image
# pod/my-pod created

kubectl get pods -w
```

```
NAME     READY   STATUS             RESTARTS   AGE
my-pod   0/1     ErrImagePull       0          3s
my-pod   0/1     ImagePullBackOff   0          15s
```

Two lessons in one screen:

1. **"pod created" is not "pod running."** The API server stored the object; the kubelet then failed to pull.
2. **`ErrImagePull` → `ImagePullBackOff`** are **two stages of the same failure** — first attempt fails, then the retries get backed off.

`amazing-me` doesn't exist on Docker Hub, and **Docker Hub is the default registry**.

### Demo B — why ubuntu "Completed" and then "CrashLoopBackOff"

```bash
kubectl run ubuntu-1 --image=ubuntu
```

Watch the left pane:

```
ubuntu-1   0/1   Pending
ubuntu-1   0/1   ContainerCreating
ubuntu-1   0/1   Completed
ubuntu-1   0/1   CrashLoopBackOff
```

**Why did it complete, and why did we never see `Running`?**

```bash
docker pull ubuntu
docker inspect ubuntu        # look at the default CMD
```

The ubuntu image's default command is **`bash`**. Started with no TTY and no input, `bash` **exits immediately** — its job is done. Container done → `Completed`.

We never saw `Running` because the whole thing took **milliseconds** — too fast for the watch to render.

**Why `CrashLoopBackOff` after `Completed`?** Because a **manually created pod defaults to `restartPolicy: Always`**. The container succeeded (exit 0), and got **restarted anyway** — repeatedly. Each restart completes just as fast, the kubelet backs off further, and the status becomes `CrashLoopBackOff`.

> This is the clearest possible demonstration of "Always restarts **regardless of exit code**."

### Demo C — `--restart=Never` + a sleep, and finally seeing `Running`

```bash
kubectl delete pod ubuntu-1

kubectl run ubuntu-2 --image=ubuntu --restart=Never -- sleep 5
```

Watch the left pane — this time you see **every** phase:

```
ubuntu-2   0/1   Pending
ubuntu-2   0/1   ContainerCreating
ubuntu-2   0/1   Running            ← 5 seconds of sleep
ubuntu-2   0/1   Completed
```

- `--restart=Never` → once it completes, it **stays** `Completed`. No restart, no `CrashLoopBackOff`.
- `-- sleep 5` **overrides the image's default `bash`** command, giving the container 5 seconds of life so the `Running` phase is visible.
- `--restart=Never` is how you get a pod to run **once** and rest quietly so you can inspect it.

> **Takeaway:** the phase you see is a function of (a) what the container's command does and (b) the restart policy. Change either and the status story changes.

---

## 8) Common Pod Errors

| Status | Meaning | Root causes | Where to look |
|---|---|---|---|
| **`CrashLoopBackOff`** | Container keeps crashing and being restarted with **exponential backoff** | Bad env vars, misconfiguration, failing probes (next lecture), **OOMKilled**, application bugs, wrong command | `kubectl logs`, `kubectl describe pod` (Last State, Reason) |
| **`ErrImagePull`** | The **first** failed pull attempt | Wrong image name/tag, private registry without valid auth, registry network/DNS issue | `kubectl describe pod` → Events |
| **`ImagePullBackOff`** | Pulling keeps failing → **backed off** retries | Same as above, after retries | `kubectl describe pod` → Events |
| **`OOMKilled`** | Container exceeded its **memory limit** and was killed | Memory limit too low, memory leak, load spike | `kubectl describe pod` (Last State → Reason: OOMKilled); raise limits (Day 19) |
| **`Unknown`** | Kubelet/node unreachable — state cannot be determined | Node down, kubelet stopped, network partition, infrastructure failure | `kubectl get nodes`, node logs, cloud provider events |
| **`Pending`** | Not scheduled / not started | No node fits requests, taints without tolerations, PVC unbound | `kubectl describe pod` → Events |
| **`ContainerCreating`** (stuck) | Runtime is preparing the container | Image pull, volume mount, CNI/DNS setup | `kubectl describe pod` → Events |

---

### CrashLoopBackOff & exponential backoff

> **Exponential backoff** = each retry waits **twice** as long as the previous one.

```
restart 1 →  10s
restart 2 →  20s
restart 3 →  40s
restart 4 →  80s
restart 5 → 160s
restart 6 → 320s  → capped
...
then → every 5 minutes, forever
```

- The delay **doubles** until it reaches the **5-minute cap**.
- After that, the kubelet retries **every 5 minutes**, indefinitely.
- This is *why* the status shows `BackOff` — the kubelet is deliberately backing off so a broken container doesn't hammer the node.

**Why you get here:** you created a workload whose policy is `Always` (Deployment / bare pod) and the container **cannot stay up**.

### ErrImagePull vs ImagePullBackOff

They are **the same failure at different stages**:

```
pull fails ──► ErrImagePull          (stage 1: the error itself)
     │
     ▼  retries with backoff
     ▼
ImagePullBackOff                     (stage 2: we've given up for now, will retry)
```

- **Image pull has its own backoff timer**, just like container restarts.
- Confirmed live in this lecture: `ErrImagePull` appeared first, then turned into `ImagePullBackOff`.

**Causes:**

- **Wrong image name or tag.**
- **Private registry with missing/incorrect authentication** — public images (`nginx`) need no credentials, but production images in private registries do.
- **Registry network connectivity** — this is exactly what broke the Day 21 demos: the internet dropped, so pulls failed even with a perfectly valid manifest.

### OOMKilled

- Container used **more memory than its `limits.memory`**.
- The kernel's OOM killer terminates the process (Day 19 — limits are enforced by cgroups, memory overrun = kill, CPU overrun = throttle).
- With `restartPolicy: Always` this becomes a **loop**: start → exceed → OOMKilled → restart → exceed → …

```bash
kubectl describe pod <pod> | Select-String -Pattern "Last State|Reason|OOMKilled" -Context 0,3
```

### Unknown

- Usually **infrastructure-level**: the node hosting the pod has a problem.
- Kubernetes has **lost communication** with the node, so it cannot report the pod's true state.
- Check the node first — `kubectl get nodes` — the pod is usually a symptom.

---

## 9) The Troubleshooting Workflow

```bash
# 1. What is the status? (and watch it change)
kubectl get pods
kubectl get pods -w

# 2. What does Kubernetes think happened? (Events is the goldmine)
kubectl describe pod <pod>

# 3. What does the app itself say?
kubectl logs <pod>                    # single-container pod
kubectl logs <pod> -c <container>     # multi-container pod (Day 21)
kubectl logs <pod> --previous         # the PREVIOUS crash's logs (crucial for CrashLoopBackOff)

# 4. Cluster-wide event stream
kubectl events

# 5. Raw object as the API server sees it (restartPolicy, imagePullPolicy, lastState)
kubectl get pod <pod> -o yaml

# 6. Node problems
kubectl get nodes
kubectl describe node <node>
```

### The instructor's ranking

| Command | When it wins |
|---|---|
| **`kubectl describe pod`** | **Most used** — Events at the bottom tell you *why* (`Failed to pull image`, `OOMKilled`, `FailedScheduling`, volume mount errors) |
| **`kubectl logs`** | Application-level failures — the app's own error message |
| **`kubectl events`** | Fast, cluster-wide view of what's happening right now |

> **For `CrashLoopBackOff`, `--previous` is non-negotiable.** The current container may not have produced any logs yet — the useful output is from the crash that already happened.

---

## 10) Key Takeaways

1. **Every termination follows the same path:** SIGTERM to **all** containers → **30 s** default grace period → SIGKILL if still alive.
2. **`terminationGracePeriodSeconds`** (pod-level) is the knob — set it **above** your app's real shutdown time (e.g. 40 s for a 35 s drain).
3. **Graceful shutdown needs a signal handler.** A broken handler or a slow shutdown both end in SIGKILL.
4. **`--force=true`** deletes the pod **object** instantly (invisible to `kubectl get pods`) while the **kubelet keeps tracking the containers**; add **`--grace-period=0`** to skip SIGTERM and SIGKILL immediately.
5. **`restartPolicy` is pod-level** — it applies to every container. `Always` (default: Deployments, StatefulSets, DaemonSets, bare pods), `OnFailure` (default: Jobs/CronJobs), `Never` (no default).
6. **Exit 0 = success, non-zero = failure.** `Always` ignores this distinction; `OnFailure` acts on it; `Never` never restarts.
7. **`imagePullPolicy` is container-level**: `Always` (dev), `IfNotPresent` (prod), `Never` (air-gapped/preloaded).
8. **Defaults come from the tag:** `latest` or **no tag** → **`Always`**; **version tag** → **`IfNotPresent`**. Always version-tag images in production.
9. **Same tag ≠ same image.** Two developers pushing the same tag can put different code on different nodes — enforce **immutable tags** in the pipeline.
10. **Phases:** `Pending` → `Running` → `Succeeded` / `Failed`; `Unknown` for infra failures. CLI shows `Completed` where docs say `Succeeded`.
11. **Pod status reflects the WORST container.** 4/5 ready with one broken container = that container's error is the pod's status.
12. **`Succeeded`/`Completed` and `Failed` only appear when the pod is not restarting** — `Always` converts a clean exit into `CrashLoopBackOff`.
13. **`CrashLoopBackOff` = exponential backoff**, 10 s → 20 → 40 → 80 … capped at **5 minutes**, then retried forever.
14. **`ErrImagePull` → `ImagePullBackOff`** are stage 1 and stage 2 of the same pull failure.
15. **`OOMKilled`** = memory limit exceeded (cgroups, Day 19) — and under `Always` it loops.
16. **Debug order:** `get pods` → `describe pod` (Events) → `logs` / `logs --previous` → `events` → `get -o yaml` → check the node.

---

## 11) Quick Reference Snippets

```yaml
# Termination behaviour
spec:
  terminationGracePeriodSeconds: 40    # default 30

# Restart behaviour (pod-level — ALL containers)
spec:
  restartPolicy: Always                # Always | OnFailure | Never

# Image pull behaviour (container-level)
spec:
  containers:
    - name: app
      image: myapp:1.2.3               # version tag → defaults to IfNotPresent
      imagePullPolicy: IfNotPresent    # Always | IfNotPresent | Never

# Private registry auth
spec:
  imagePullSecrets:
    - name: regcred
```

```bash
# Delete variations
kubectl delete pod <pod>
kubectl delete pod <pod> --force=true
kubectl delete pod <pod> --force=true --grace-period=0

# Run a pod once and inspect it later
kubectl run <pod> --image=ubuntu --restart=Never -- sleep 5

# Watch phases live
kubectl get pods -w

# Diagnose
kubectl describe pod <pod>
kubectl logs <pod> -c <container>
kubectl logs <pod> --previous
kubectl events
kubectl get pod <pod> -o yaml

# Image inspection (Docker, for understanding default commands)
docker pull ubuntu
docker inspect ubuntu
```

---

## 12) Quick Self-Check

1. A pod is deleted. In what order are signals sent, and what is the default timeout?
2. Your app needs 35 s to drain connections. What do you set, and where?
3. You run `kubectl delete pod p --force=true`. Does `kubectl get pods` show `p`? Are the containers guaranteed stopped?
4. What does `--grace-period=0` change compared to plain `--force`?
5. Which is pod-level and which is container-level: `restartPolicy`, `imagePullPolicy`?
6. What policy do Deployments default to? Jobs? Bare pods?
7. A container exits 0. Under which policy does it restart anyway? Under which does it stay `Completed`?
8. You push `nginx:latest` to prod and the image is already cached on the node. Will Kubernetes re-pull on restart? Why?
9. Why is `IfNotPresent` risky if two developers can push the same tag?
10. A pod shows `4/5` with `ErrImagePull`. Explain what the `5` and the `4` mean.
11. Why did `kubectl run ubuntu-1 --image=ubuntu` go `Completed` and then `CrashLoopBackOff`?
12. What's the difference between `ErrImagePull` and `ImagePullBackOff`?
13. Write the exponential backoff sequence up to the cap. What happens after the cap?
14. Which `kubectl logs` flag do you need for a container that keeps crashing?

---

## What's Next (Day 23)

- **Health probes** — liveness, readiness, and startup probes: how Kubernetes checks that a container is alive, ready for traffic, and finished booting.

---

*End of Day 22 notes.*
