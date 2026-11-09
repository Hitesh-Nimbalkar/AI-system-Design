# Kubernetes Requests, Limits & LimitRange — Complete Notes (Day 19)

> Source: Day 19 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Mastering Kubernetes requests, limits, and LimitRange to prevent Noisy Neighbor issues and ensure fair resource distribution.
> How to use: Read one chunk at a time, answer the recall questions, then move to the next chunk.

---

## 1) Incremental Learning Prompt (Copy/Paste)

```text
Act as my incremental Kubernetes tutor for a CKA course.

Source material: Day 19 lecture on Kubernetes requests, limits, and LimitRange — the Noisy Neighbor problem, requests vs limits, CPU units, how the scheduler uses requests, how the kernel enforces limits (CPU throttling vs OOM kills), cgroups, metrics-server, kubectl top, and LimitRange defaults/min/max.

Teach me incrementally, not all at once.

Rules:
1. Break the lecture into small chunks (5–10 minutes each).
2. For each chunk, give:
   - Learning goal
   - Simple explanation
   - Key terms/definitions
   - One analogy
   - 2–3 active-recall questions
   - One small practice/thinking task
3. Wait for my answer before moving to the next chunk.
4. Track progress with a checklist.
5. Correct my misconceptions gently.
6. Use beginner-friendly language and connect ideas to real CKA/DevOps work.
7. Start by giving me the roadmap, then teach only Chunk 1.

Topic: Kubernetes requests, limits, and LimitRange from Day 19 of a CKA course.
```

---

## 2) Progress Tracker

- [x] Chunk 1: The Noisy Neighbor problem
- [x] Chunk 2: Requests vs limits — definitions
- [x] Chunk 3: CPU units and how to read them
- [x] Chunk 4: Benefits of requests and limits
- [x] Chunk 5: Where to define requests/limits (container vs pod level)
- [x] Chunk 6: Other resources — ephemeral storage
- [x] Chunk 7: How the scheduler uses requests
- [x] Chunk 8: How the kernel enforces limits (throttle vs kill)
- [x] Chunk 9: Metrics server and `kubectl top`
- [x] Chunk 10: Demo — memory limit and OOMKilled
- [x] Chunk 11: Control groups (cgroups)
- [x] Chunk 12: Demo — CPU limits and throttling
- [x] Chunk 13: LimitRange — defaults, min, max
- [x] Chunk 14: Recap and best practices

---

## Chunk 1: The Noisy Neighbor problem

**Learning goal:** Understand the real-world problem requests and limits solve.

### The scenario from the lecture

- Kubernetes cluster with **two worker nodes** (node1, node2).
- Each node: **6 vCPUs and 24 GB memory**.
- Two deployments: **deployment1** and **deployment2**.
- Each deployment has **2 pods**; each node runs 1 pod from each deployment.
- Each pod has **one container**.
- Everything works fine at first.

### What goes wrong

- Deployment2 has a **bug in the code**.
- Both deployment2 pods start **consuming all node resources**.
- Deployment1 pods — which were healthy — now suffer **resource starvation**.
- The deployment2 containers became a **Noisy Neighbor**: they disrupted other workloads on the same node.

### Key takeaway

Without requests and limits, one misbehaving workload can starve every other workload on the node. Requests and limits prevent this.

### Active recall

1. What is a “Noisy Neighbor” in Kubernetes?
2. Why did deployment1 suffer even though its own code was fine?
3. What two mechanisms does Kubernetes give us to prevent this?

### Practice task

Draw the cluster from the lecture (2 nodes × 6 vCPU / 24 GB, 2 deployments × 2 pods) and label which pods become noisy.

---

## Chunk 2: Requests vs limits — definitions

**Learning goal:** Clearly distinguish requests from limits.

### Requests

- **Minimum guaranteed resources** (typically CPU and memory) for a container.
- Used by the **scheduler** to decide which node can host the pod.
- If a node cannot satisfy the request, the pod is **not scheduled** there.

### Limits

- A **ceiling**: the **maximum** resources a container can use.
- Enforced at runtime by the **Linux kernel** via cgroups.
- CPU above the limit → **throttled**.
- Memory above the limit → **OOMKilled**.

### Example from the lecture

```yaml
resources:
  requests:
    cpu: "1"
    memory: "2Gi"
  limits:
    cpu: "2"
    memory: "4Gi"
```

Meaning:

- Container is **guaranteed** 1 CPU and 2 Gi memory.
- Container may **burst up to** 2 CPU and 4 Gi memory **if the node has spare capacity**.

### Key takeaway

- Request = “reserve this much for me.”
- Limit = “never let me exceed this.”

### Active recall

1. Who uses requests — the scheduler or the kernel?
2. Who enforces limits — the scheduler or the kernel?
3. If a container’s request is 1 CPU and its limit is 2 CPU, how much CPU is it guaranteed? How much can it use?

### Practice task

Write the YAML `resources` block for a container that requests 250m CPU / 128Mi memory and has limits of 500m CPU / 256Mi memory.

---

## Chunk 3: CPU units and how to read them

**Learning goal:** Read and write CPU values correctly.

### Physical vs virtual CPU

- On bare metal, you may hear “CPU” meaning a **physical CPU**.
- With **hyperthreading enabled**, 12 physical CPUs ≈ **24 virtual CPUs (vCPUs)** or 24 cores.
- In cloud and VM-based Kubernetes clusters, `cpu: 1` usually means **1 vCPU**.

### Fractional CPUs — the `m` (milli) suffix

- `1 CPU = 1000m`
- `1000m` = 1 CPU
- `500m` = 0.5 CPU (half)
- `250m` = 0.25 CPU (quarter)
- `100m` = 0.1 CPU (one tenth)

You can write CPU either as a decimal (`0.9`) or with milli (`900m`).

### Memory units

- `Mi` = mebibytes, `Gi` = gibibytes (binary units).
- `M` = megabytes, `G` = gigabytes (decimal units).
- Kubernetes commonly uses **Mi / Gi** in manifests.

### Key takeaway

- `1000m = 1 CPU`.
- `500m = 0.5 CPU`.
- `900m = 0.9 CPU`.

### Active recall

1. How many millicores is 1 CPU?
2. What is `250m` in CPU terms?
3. Is `900` the same as `900m`? (Yes — 900 means 0.9 CPU.)

### Practice task

Convert the following to millicores: `0.1 CPU`, `0.75 CPU`, `2 CPUs`. Then convert `1500m` back to CPU.

---

## Chunk 4: Benefits of requests and limits

**Learning goal:** Know the four benefits the lecture highlights.

### The four benefits

1. **Efficient resource allocation**
   - Resources are used optimally across the cluster.
2. **Avoidance of resource starvation**
   - Prevents one workload from hogging everything.
3. **Cluster stability**
   - Kubernetes can schedule and manage workloads predictably because every container has a defined request and limit.
4. **Mitigation of the Noisy Neighbor problem**
   - Prevents one workload from disrupting others.

### Key takeaway

Always define requests and limits for your containers — it is a Kubernetes **best practice** and essential for stability.

### Active recall

1. List the four benefits.
2. Which benefit directly addresses the deployment2 scenario?
3. Why does cluster stability depend on requests and limits being defined?

### Practice task

In your own words, explain to a teammate why “just letting pods use whatever they want” is dangerous.

---

## Chunk 5: Where to define requests and limits

**Learning goal:** Know the scope of resource definitions.

### Container level (default and recommended)

- Pods can have **multiple containers**.
- Each container has its own CPU/memory needs.
- Define `resources` **per container** — this is the standard and recommended approach.

### Pod level (newer feature)

- Since **Kubernetes 1.32**, you can define pod-level resource specifications.
- Example from the lecture: a pod with two containers (`app` and `log-aggregator`) has `resources` at the **pod level**.
- The instructor’s recommendation: **define requests and limits per container**, even though pod-level is available.

### Key takeaway

Default to **per-container** resources. Pod-level is available in 1.32+ but container-level is clearer and preferred.

### Active recall

1. At which level are requests and limits normally defined?
2. What version introduced pod-level resource specifications?
3. Why does the instructor recommend container-level?

### Practice task

Look at a pod with two containers and write the `resources` block for each one separately.

---

## Chunk 6: Other resources — ephemeral storage

**Learning goal:** Know that CPU and memory are not the only resources you can constrain.

### Other resource types

You can define requests and limits not just for CPU and memory but also for:

- `ephemeral-storage`
- Other project-specific resources (the lecturer leaves these to documentation reading).

### Ephemeral storage

- Each node has its **own local storage**.
- Production clusters typically use **NFS, SAN, or external storage** for persistent data.
- But by **default**, containers and pods write **logs and temporary data to the node’s local disk**.
- If a container writes too much locally, it can fill the node’s disk and affect everything.
- To prevent this, define `ephemeral-storage` requests and limits.

### Example from the lecture

```yaml
resources:
  requests:
    ephemeral-storage: "2Gi"
  limits:
    ephemeral-storage: "2Gi"
```

### Key takeaway

Control **ephemeral storage** to prevent a container from filling the node’s local disk with logs/temp data.

### Active recall

1. Where do pods write logs and temp data by default?
2. Why is controlling ephemeral storage important?
3. What resource key do you use in the resources block?

### Practice task

Add `ephemeral-storage` requests/limits to the earlier YAML example.

---

## Chunk 7: How the scheduler uses requests

**Learning goal:** Understand how requests affect pod scheduling.

### The mechanics

- Node1 has **6 vCPUs / 24 GB**.
- Each container requests **1 CPU / 2 Gi**.
- With 2 containers on node1 → 2 vCPUs reserved for requests.
- If you spin up **6 such containers**, node1 is **fully booked by requests**.
- Attempting a **7th container** (even requesting only `500m` or `250m`) → pod **stays Pending**.
- The **scheduler** sees no free request capacity and refuses to schedule.

### Connection to Day 15

- The scheduler checks several things before binding a pod to a node:
  - Taints and tolerations
  - Affinity / anti-affinity
  - **Resource availability** ← this one
- The scheduler knows how much is available because you defined **requests**.

### Key takeaway

Requests are the currency the scheduler uses. No request capacity left → pod is not scheduled.

### Active recall

1. If node1 has 6 vCPU and every container requests 1 CPU, how many such containers can it schedule (ignoring other overhead)?
2. What happens to a 7th pod?
3. Which Day 15 scheduler consideration does this illustrate?

### Practice task

Node2 has 8 vCPU. Containers request 500m each. How many can be scheduled before the node is “booked out” on requests?

---

## Chunk 8: How the kernel enforces limits

**Learning goal:** Understand CPU throttling vs memory OOMKill.

### Bursting above requests

- A container can **exceed its request** and burst up to its **limit** if the node has spare capacity.
- The request is a floor, not a cap.

### Exceeding limits — CPU

- If the container tries to use **more CPU than its limit**, the **Linux kernel throttles** it.
- Not the scheduler. Not Kubernetes. The **kernel**.
- Example: limit 2 CPU → container can never exceed 2 CPU.

### Exceeding limits — memory

- If the container tries to use **more memory than its limit**, the **kernel may terminate the pod** — **OOMKilled** (Out Of Memory).
- The word “may” appears because the docs say the kill happens when the kernel detects **memory pressure**.
- The lecturer notes that in practice, most kernels kill the container **as soon as it exceeds the memory limit**, regardless of node pressure. (We’ll prove this in the demo.)

### Key takeaway

- **CPU over limit → throttled.**
- **Memory over limit → OOMKilled.**

### Active recall

1. Who throttles CPU — Kubernetes or the kernel?
2. What does OOMKilled mean?
3. Does the documentation say memory over-limit *always* kills the pod? Explain.

### Practice task

Describe what happens to a container with `limits.cpu: 1` and `limits.memory: 512Mi` if it tries to use 2 CPU and 600Mi.

---

## Chunk 9: Metrics server and `kubectl top`

**Learning goal:** Learn how to see resource usage in the cluster.

### `kubectl top`

- Works like Linux `top`.
- `kubectl top nodes` → shows node CPU/memory utilization.
- `kubectl top pods` → shows pod CPU/memory utilization.

### The error seen in the lecture

```
error: Metrics API not available
```

- `kubectl top` relies on an **add-on** called **metrics-server**.
- If metrics-server is not installed, you get this error.

### How metrics flow (simplified + corrected)

- Every worker node runs **kubelet**.
- Kubelet includes **cAdvisor** (container advisor), which exposes an API collecting metrics from nodes and pods.
- Kubelet delivers these metrics to **metrics-server**.
- The **API server** queries metrics-server when you run `kubectl top`.

> The lecturer corrects the oversimplification: it’s not that “kubelet collects” — **cAdvisor (inside kubelet)** collects, and kubelet delivers.

### Installing metrics-server (kind cluster caveat)

- Standard install: `kubectl apply -f <metrics-server.yaml>`
- For **kind** clusters, add the flag:
  ```
  --kubelet-insecure-tls
  ```
  because kind uses self-signed certificates metrics-server doesn’t trust.
- Add this flag in the **deployment** section of `components.yaml`.

### Verifying

- `kubectl get pods -n kube-system` → metrics-server pod running.
- `kubectl top nodes` → now returns CPU/memory stats.
- `kubectl top pods` → pod-level stats.

### Key takeaway

`kubectl top` needs **metrics-server**; kubelet’s **cAdvisor** feeds it. On kind, install with `--kubelet-insecure-tls`.

### Active recall

1. What add-on is required for `kubectl top`?
2. What component inside kubelet actually collects the metrics?
3. What extra flag is needed on kind clusters, and why?

### Practice task

List the exact commands to install metrics-server on a kind cluster and verify it works.

---

## Chunk 10: Demo — memory limit and OOMKilled

**Learning goal:** See memory limits enforced in practice.

### The manifest

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: memory-demo
spec:
  containers:
    - name: memory-demo-ctr
      image: polinux/stress
      resources:
        requests:
          memory: "100Mi"
        limits:
          memory: "200Mi"
      command: ["stress"]
      args: ["--vm", "1", "--vm-bytes", "190M", "--vm-hang", "1"]
```

- `stress` simulates memory load.
- Request 100Mi → scheduler only places this pod on a node with ≥100Mi free.
- Limit 200Mi → hard ceiling.
- Load 190M → **under** the limit → container runs fine.
- `kubectl top pods` shows ~193Mi, stays under 200Mi, **no OOMKill**.

### Bump load to 250M

- Edit the manifest, change `190M` → `250M`, apply.
- `kubectl get pods -o wide` → shows **OOMKilled**.
- Even though the **node had plenty of memory**, the pod was still killed.
- This contradicts the “kills only under memory pressure” reading of the docs.

### Why?

- Because the **kernel** kills any process exceeding its **cgroup memory limit**.
- Some kernels are relaxed, but most in the wild kill immediately. (See Chunk 11 for the cgroup explanation.)

### After OOMKill

- Pod enters **CrashLoopBackOff** — kubelet keeps restarting it.
- `kubectl delete pod memory-demo` to clean up, then revert to `190M` if you want it running.

### Key takeaway

Memory limit breach → **OOMKilled**, typically regardless of node pressure, because the kernel enforces the **cgroup limit**.

### Active recall

1. Why did the first pod (190M load) stay Running?
2. Why did the second pod (250M load) get OOMKilled?
3. What state does the pod go into after repeated OOMKills?

### Practice task

Given a pod with `limits.memory: 256Mi`, what would happen if you set stress to `300M`?

---

## Chunk 11: Control groups (cgroups)

**Learning goal:** Understand the Linux feature underneath limits.

### What is a cgroup?

- A **Linux kernel feature** — not a Kubernetes concept.
- Creates **resource boundaries** for processes: memory, CPU, disk I/O, etc.
- If a process exceeds its cgroup boundary, the **kernel kills or throttles** it.

### How it connects to pods

1. **kubelet** receives instructions from the **API server**: “create this pod with these containers and specs.”
2. kubelet invokes the **container runtime** (containerd, CRI-O, Podman, etc.).
3. The runtime:
   - Pulls the image from the registry if not cached.
   - Configures networking via the **CNI plugin**.
   - Mounts volumes defined in the pod spec.
   - Creates and starts the containers.
   - **Creates a cgroup for each container** — always, regardless of whether resources are defined.
4. If the container has `resources`, those requests/limits go **into the cgroup**.
5. The **Linux kernel** sees the process exceeding the cgroup limit → **kills** (memory) or **throttles** (CPU).

### Why the docs say “may”

- The kernel can be configured to be **relaxed** and allow some overage.
- But most kernels (and the lecturer’s experience) kill immediately on memory limit breach.

### Key takeaway

For the Linux kernel, pods are just **processes** in **cgroups**. Exceeding the cgroup memory limit → killed. Exceeding CPU limit → throttled.

### Active recall

1. Is a cgroup a Kubernetes object or a Linux feature?
2. Who creates the cgroup for a container?
3. Why does the kernel kill the pod even when the node has free memory?

### Practice task

Trace the path: `kubectl apply` → API server → kubelet → container runtime → cgroup → kernel enforcement.

---

## Chunk 12: Demo — CPU limits and throttling

**Learning goal:** See CPU limits enforced in practice.

### The manifest

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: cpu-demo
spec:
  containers:
    - name: cpu-demo-ctr
      image: vish/stress
      resources:
        requests:
          cpu: "500m"
        limits:
          cpu: "900m"
      args:
        - -cpus
        - "1"
```

- Request 500m → scheduled only if node has ≥500m free CPU.
- Limit 900m → hard ceiling at 0.9 CPU.
- Load `-cpus 1` → asks for 1 full CPU → **exceeds** limit.

### Result

- `kubectl top pods` shows **~898m**, never 1000m.
- The kernel throttles the container to 900m.
- Even though the app wants 1 CPU, it can never get more than 900m.
- `kubectl describe node <worker1>` → shows the pod’s requests and limits in the **Allocated resources** section.

### Key takeaway

CPU limits are enforced by **throttling**, and you can verify usage with `kubectl top pods` and `kubectl describe node`.

### Active recall

1. Why does `kubectl top` show ~898m instead of 1000m?
2. Where in `kubectl describe node` can you see all pods’ requests/limits?
3. What would happen if the limit were removed?

### Practice task

Describe what `kubectl top pod` would show for a container with `limits.cpu: 250m` running a 1-CPU stress test.

---

## Chunk 13: LimitRange — defaults, min, max

**Learning goal:** Enforce resource definitions at the namespace level.

### The problem

- Not everyone will define requests/limits.
- A pod without them can run and hog everything — breaking the Noisy Neighbor prevention.
- We need a **namespace-level policy** so every pod gets some defaults and bounds.

### Enter `LimitRange`

- A **namespace-scoped** object.
- Verifiable with:
  ```
  kubectl api-resources | grep -i limit
  ```
  → `limitranges`, `namespaced: true`.
- Defined in **each namespace** where you want it enforced.

### The manifest (from the lecture)

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: resource-limits
spec:
  limits:
    - type: Container
      default:
        cpu: "2"
        memory: "4Gi"
      defaultRequest:
        cpu: "1"
        memory: "2Gi"
      max:
        cpu: "2"
        memory: "4Gi"
      min:
        cpu: "500m"
        memory: "128Mi"
```

### What each field does

| Field | Meaning |
|---|---|
| `default` | Limit applied if the container has **no limit** |
| `defaultRequest` | Request applied if the container has **no request** |
| `max` | Hard cap — container **cannot request/limit above this** |
| `min` | Floor — container **cannot request/limit below this** |

### Apply and verify

```
kubectl apply -f limitrange.yaml
kubectl describe limitranges resource-limits
```

### Test — pod with no resources

```
kubectl run my-pod --image=nginx
kubectl describe pod my-pod
```

- The pod gets **request 1 CPU / 2Gi** and **limit 2 CPU / 4Gi** automatically (the defaults).

### Test — pod below `min`

- Set `requests.cpu: 400m` in the manifest → apply.
- Error:
  ```
  Forbidden: minimum CPU usage per container is 500m, but request is 400m
  ```
- The API server **rejects** the pod.

### Key takeaway

LimitRange ensures:
- Pods **without** resources get sensible **defaults**.
- Pods **below min** or **above max** are **rejected**.
- This completes the Noisy Neighbor prevention story — even lazy manifests can’t escape.

### Active recall

1. Is LimitRange namespace-scoped or cluster-scoped?
2. What is the difference between `default` and `defaultRequest`?
3. What happens if a pod requests **below** the `min`?
4. What happens if a pod requests **above** the `max`?

### Practice task

Write a LimitRange for a `dev` namespace that defaults to 250m CPU / 256Mi and 500m CPU / 512Mi limits, with `min.cpu: 100m` and `max.cpu: "1"`.

---

## Chunk 14: Recap and best practices

**Learning goal:** Consolidate everything from Day 19.

### Core ideas

1. **Requests** = guaranteed / scheduling currency. **Limits** = ceiling / kernel enforcement.
2. **CPU over limit → throttled** by the kernel.
3. **Memory over limit → OOMKilled** by the kernel via cgroups.
4. **The scheduler** uses requests to decide placement.
5. **kubectl top** needs **metrics-server**; kubelet’s **cAdvisor** provides the data.
6. **cgroups** are the Linux mechanism behind limits.
7. **LimitRange** enforces defaults, min, and max per namespace.
8. **Kubernetes 1.32+** supports pod-level resources, but **per-container** is still the recommendation.

### Best practices

- Always define **requests and limits** for every container.
- Prefer **per-container** resources over pod-level.
- Use **LimitRange** in every namespace to catch manifests that forget.
- Consider **ephemeral-storage** limits to prevent disk-fill issues.
- Use `kubectl top`, `kubectl describe node`, and `kubectl describe pod` to **verify** enforcement.

### What’s next (Day 20)

- Kubernetes autoscaling.
- **HPA** — Horizontal Pod Autoscaler.
- **VPA** — Vertical Pod Autoscaler.

### Active recall

1. Summarize requests vs limits in two sentences.
2. What are the four benefits of defining resources?
3. What problem does LimitRange solve that requests/limits alone cannot?
4. Name three commands you’d use to verify resource enforcement in a cluster.

### Practice task

Write a 5-bullet “cheat sheet” for Day 19 that you could hand to a new teammate.

---

## Suggested Answer Key

### Chunk 1

1. A pod/container that consumes excessive node resources and degrades other workloads sharing the node.
2. It shared the same nodes with the noisy deployment2 pods, which consumed the node’s CPU and memory.
3. Requests (for scheduling) and limits (for runtime enforcement).

### Chunk 2

1. The scheduler.
2. The Linux kernel.
3. Guaranteed 1 CPU; can use up to 2 CPU if the node has spare capacity.

### Chunk 3

1. `1000m`.
2. A quarter of a CPU.
3. Yes — 900 CPU = 900m = 0.9 CPU.

### Chunk 4

1. Efficient allocation; avoid starvation; cluster stability; mitigate Noisy Neighbor.
2. Mitigation of Noisy Neighbor.
3. Scheduler can predict placement and prevent overcommit surprises.

### Chunk 5

1. Per-container (normally).
2. Kubernetes 1.32.
3. Each container has its own needs; it’s clearer and standard.

### Chunk 6

1. The node’s local disk (unless external storage is mounted).
2. Prevents a container from filling the node disk with logs/temp data and affecting others.
3. `ephemeral-storage`.

### Chunk 7

1. Six (6 vCPU / 1 vCPU each).
2. It stays Pending — the scheduler can’t find request capacity.
3. Resource availability.

### Chunk 8

1. The Linux kernel.
2. Out-Of-Memory kill — kernel terminates the container for exceeding memory limit.
3. No — docs say “may” kill on memory pressure; in practice most kernels kill on limit breach.

### Chunk 9

1. metrics-server.
2. cAdvisor (inside kubelet).
3. `--kubelet-insecure-tls`, because kind uses self-signed certs not trusted by metrics-server.

### Chunk 10

1. 190M load was under the 200Mi limit → allowed.
2. 250M load exceeded the 200Mi limit → kernel OOMKilled it.
3. CrashLoopBackOff.

### Chunk 11

1. Linux kernel feature.
2. The container runtime.
3. Because the kernel enforces the cgroup memory limit, which triggers OOMKill regardless of node pressure.

### Chunk 12

1. The kernel throttles the container at its 900m limit.
2. In the “Allocated resources” table of `kubectl describe node`.
3. The container could use all available CPU on the node (still bounded by the scheduler’s accounting for requests of other pods).

### Chunk 13

1. Namespaced.
2. `default` is the limit applied when none is set; `defaultRequest` is the request applied when none is set.
3. The API server rejects the pod with a Forbidden error.
4. The API server rejects the pod.

### Chunk 14

1. Requests guarantee minimum resources and drive scheduling; limits cap maximum use and are enforced by the kernel (throttle CPU, kill on memory).
2. Efficient allocation, avoid starvation, cluster stability, Noisy Neighbor mitigation.
3. It ensures pods **without** resource definitions still get defaults, and rejects pods below min / above max.
4. `kubectl top pods`, `kubectl describe node`, `kubectl describe pod`.

---

## Final Recap

Day 19 showed **why** requests and limits exist (Noisy Neighbor), **how** they work (scheduler uses requests; kernel enforces limits via cgroups), and **how to guarantee** they’re always present (LimitRange defaults/min/max). The demos proved the theory: memory over-limit → OOMKilled even without node pressure; CPU over-limit → throttled at the limit. LimitRange closes the last gap by forcing defaults on pods that forget.

---

*End of complete Day 19 notes.*