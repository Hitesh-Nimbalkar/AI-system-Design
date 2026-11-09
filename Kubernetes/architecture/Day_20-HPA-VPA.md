# Kubernetes Autoscaling — HPA & VPA — Complete Notes (Day 20)

> Source: Day 20 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Horizontal Pod Autoscaler (HPA) and Vertical Pod Autoscaler (VPA).
> Prerequisite: Day 19 (requests/limits, metrics-server, cgroups).

---

## CKA Exam Curriculum Update

- The CKA exam was updated on **February 18, 2025**.
- In the **Workloads & Scheduling** section, the syllabus says: **“Configure workload autoscaling.”**
- It does **not** name HPA or VPA specifically — so you must know **both**.
- The exam now uses **Kubernetes v1.32**.
- The lecture cluster runs **v1.31** (client 1.31.1, server 1.31.4). Upgrade is done by editing the **kind cluster YAML** to point at 1.32 (link provided in the GitHub notes).

---

## What is Scaling?

**Scaling** = adjusting the resources available to an application based on **demand and load**.

- As load increases → resources increase.
- As load decreases → resources decrease.

Scaling is a general concept that applies to **both VMs and pods**.

### Two types of scaling

| Type | Meaning | Direction |
|---|---|---|
| **Horizontal** | Increase/decrease the **number of servers or pods** | Scale **out** (add) / Scale **in** (remove) |
| **Vertical** | Increase/decrease the **resources of the same server or pod** | Scale **up** (more resources) / Scale **down** (fewer resources) |

### Memory aid

- **Horizontal** → horizontal arrow → you add more units side-by-side.
- **Vertical** → upright arrow → you climb up/down a ladder (up/down).

### Important: vertical scaling requires a restart

- Vertical scaling a **pod** → warrants a **pod restart**.
- Vertical scaling a **VM/EC2 instance** (e.g., changing instance type in AWS) → requires **power off → change type → power on**.

### Modern preference

Cloud-native applications **prefer horizontal scaling** (scale out) because:
- No restart required.
- Better fault tolerance.
- More predictable.

Vertical scaling is used but is **less preferred** because of the restart requirement.

---

## Manual vs Automatic Scaling

### Horizontal scaling — two approaches

1. **Manual**
   - Edit the deployment YAML and change `replicas`, then `kubectl apply`.
   - Or run:
     ```
     kubectl scale deployment my-deploy --replicas=2
     ```
2. **Automatic**
   - Achieved with **Horizontal Pod Autoscaler (HPA)**.
   - Preferred in production because load varies by time of day, weekends, etc.

### Vertical scaling — two approaches

1. **Manual**
   - Change `requests` and `limits` in the pod spec and recreate the pod (restart required).
2. **Automatic**
   - Achieved with **Vertical Pod Autoscaler (VPA)** — pod restart required to apply.

---

## Scaling the Underlying Nodes

Pods need nodes. When pod load grows, nodes must also be able to scale.

### Horizontal scaling of nodes

- **Cluster Autoscaler** (most common).
- **Karpenter** (AWS-focused alternative).
- Both can be used to add/remove worker nodes.

### Vertical scaling of nodes

- **Not used in production.**
- Requires powering off the node and increasing resources — which would evict all pods on the node. Futile.

### Node groups — a common production pattern

Cloud providers offer nodes with different configurations:

- **High-memory nodes**
- **GPU nodes**
- **SSD / high-IOPS nodes**
- **High-CPU compute nodes**

In production:

1. Create a **node group** per configuration (e.g., `ng1` = high-memory, `ng2` = GPU, etc.).
2. Nodes inside a node group share the **same configuration**.
3. Apply **cluster-autoscaler** or **Karpenter** to **individual node groups**.

This is the standard production setup.

---

## Horizontal Pod Autoscaler (HPA)

### What it is

HPA **automatically scales the number of pods** based on **observed metrics** such as:
- CPU utilization
- Memory utilization
- Custom metrics (more on these below)

### Prerequisites

- **metrics-server must be installed.**
- Requests and limits must be set on containers (from Day 19) — HPA depends on them.

### How it works (control loop)

- The **HPA controller** checks utilization with **metrics-server** every **15 seconds**.
- Like most Kubernetes objects, HPA has its own controller.
- When the metric crosses the **target**, HPA scales **out** (add pods) or **in** (remove pods).

### Supported workloads

- **Deployment** (primary — this is what you'll use in the exam).
- **StatefulSet**.
- ReplicationController and ReplicaSet are technically supported but rarely used.

### Metrics flow (CPU/memory path)

```
pods & nodes → cAdvisor (inside kubelet) → kubelet → metrics-server
                                                          ↓
                                       exposes metrics.k8s.io API
                                                          ↓
                                                    HPA controller
                                                          ↓
                                                 scale in / scale out
```

The API `metrics.k8s.io` is what HPA queries for CPU/memory metrics. This is the same path `kubectl top` uses.

### Why custom metrics?

CPU and memory are **not always** the right scaling signal. Examples:

- **Network-sensitive** app → scale on **network latency**.
- **Storage-sensitive** app → scale on **IOPS**.
- **Queue-based** app → scale on **SQS queue length**.
- **Pub/sub** app → scale on **SNS metrics**.

For these cases, you need **custom metrics** — metrics that come from **outside CPU and memory**.

### Custom metrics — the full picture

Two categories:

1. **Internal metrics** — from Kubernetes objects themselves (deployments, pods, nodes).
2. **External metrics** — from systems **outside** Kubernetes (e.g., Amazon SQS, SNS, Azure Functions).

To make these available:

```
Prometheus (or Zabbix/New Relic/etc.)
      ↓ collects metrics from internal + external sources
Prometheus Adapter
      ↓ converts Prometheus metrics → Kubernetes API format
custom.metrics.k8s.io   (internal resources)
external.metrics.k8s.io (external resources)
      ↓
HPA controller queries these APIs and scales
```

- **`custom.metrics.k8s.io`** → for internal Kubernetes object metrics.
- **`external.metrics.k8s.io`** → for external systems.

### Exam note

You will **not be asked about custom metrics** in the CKA exam. But in production, application-specific metrics (e.g., HTTP requests per second) are commonly used.

---

## HPA Demo

### Setup

- metrics-server is **already installed** (from Day 19).
- `kubectl top nodes` works; `kubectl top pods` shows no data until pods have requests defined.

### The deployment + service YAML (`nginx-hpa.yaml`)

- Deployment `nginx-deploy`:
  - `replicas: 1`
  - Label: `app=nginx`
  - Container `nginx-container` with:
    - `requests.cpu: 100m`
    - `limits.cpu: 200m`
- ClusterIP Service `nginx-svc`:
  - Selector `app=nginx`
  - Used by the load generator to spread traffic across pods.

```
kubectl apply -f nginx-hpa.yaml
```

### Creating the HPA from the CLI

```
kubectl autoscale deployment nginx-deploy --min=1 --max=5 --cpu-percent=50
```

Meaning:
- **min 1 pod** even with no load.
- **max 5 pods**.
- Scale out when **average CPU utilization hits 50%** of request.

### If you omit `--cpu-percent`

The **default target is 80%** CPU utilization.

### Verify

```
kubectl get hpa nginx-deploy
kubectl describe hpa nginx-deploy
```

Output shows:
- Reference: `Deployment/nginx-deploy`
- Current CPU: e.g. `0% / 50%`
- Min replicas: 1
- Max replicas: 5
- Current replicas: 1

`describe` also shows "desired count is within the acceptable range" when no scaling is needed.

### Generating load

```
kubectl run load-generator-1 --image=busybox --rm -it -- /bin/sh -c \
  "while true; do wget -q -O- http://nginx-svc; done"
```

- `--rm` → pod is deleted when you exit.
- `-it` → interactive terminal.
- Infinite loop `wget` against `nginx-svc` drives CPU load.

Run a **second** load generator in another terminal (`load-generator-2`) to push utilization higher.

### Watching HPA react

```
kubectl get hpa nginx-deploy
```

- Utilization shoots to e.g. **119%** (of the 100m request).
- Within seconds, HPA scales pods **up**.
- `kubectl get pods` → now shows **3 replicas** even though we started with 1.

### `kubectl describe hpa` after scaling

Shows events like:

```
Successful rescale: new size: 3; reason: cpu resource utilization
(percentage of request) above target
```

### `kubectl events`

Same information can be seen with:

```
kubectl events
```

### Why utilization stayed at 62%

Once at 3 replicas, the CPU load spread out. HPA **caps at max=5** — if `--max` were higher, it would have added a 6th pod.

### Cleanup

```
kubectl delete hpa nginx-deploy
kubectl delete -f nginx-hpa.yaml
```

Then `Ctrl+C` in each load-generator terminal → both load-generator pods auto-delete because of `--rm`.

---

## Vertical Pod Autoscaler (VPA)

### What it is

VPA **automatically adjusts the CPU and memory requests/limits** of your pods based on **actual usage**.

- Does **not** change replica count (unlike HPA).
- **Requires a pod restart** to apply new resource values.
- Still uses **requests and limits** (from Day 19) as its lever.

### VPA components (installed via the autoscaler repo)

VPA installation creates **three deployments** (plus RBAC, APIService, etc.):

1. **VPA Recommender**
   - Continuously analyzes **historical and current** usage.
   - Recommends **optimal CPU and memory** values.
2. **VPA Updater**
   - Identifies pods that need resource adjustments.
   - **Evicts and restarts** them to apply new settings.
   - **Respects PodDisruptionBudgets (PDBs)** to maintain availability.
3. **VPA Admission Controller**
   - **Intercepts pod creation requests**.
   - **Modifies CPU/memory requests at creation time** based on the latest recommendation.

### Installing VPA

```
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh    # or the documented install command from the notes
```

Verify:

```
kubectl get pods -n kube-system | grep vpa
```

You should see:
- `vpa-recommender-...`
- `vpa-updater-...`
- `vpa-admission-controller-...`

Check the resource exists:

```
kubectl api-resources | grep -i vertical
```

→ `verticalpodautoscalers` (short name `vpa`), namespaced, kind `VerticalPodAutoscaler`.

### VPA UpdatePolicy modes

| Mode | Behavior |
|---|---|
| **Off** | Only **recommends** — does not apply, does not restart pods. |
| **Initial** | Sets recommended resources **at pod creation**. Does not change afterward. |
| **Auto** | **Continuously** updates requests and **restarts pods as needed** based on recommendations. |

### The VPA manifest (`vpa.yaml`)

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: nginx-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nginx-deploy
  updatePolicy:
    updateMode: "Auto"
```

- `targetRef` points to the workload whose pods VPA manages.
- `updateMode: Auto` → VPA applies recommendations and restarts pods.

---

## VPA Demo

### Deploy the workload (`nginx-vpa.yaml`)

- Deployment `nginx-deploy` with `replicas: 2`.
- Container with `requests.cpu: 100m` and `limits.cpu: 100m`.
- Matching ClusterIP Service `nginx-svc` (spreads traffic across replicas).

Apply:

```
kubectl apply -f nginx-vpa.yaml
kubectl get pods
kubectl describe pod <pod-name>
```

The pod starts with the **100m** requests/limits you set.

### Apply the VPA object

```
kubectl apply -f vpa.yaml
kubectl get vpa nginx-vpa
kubectl describe vpa nginx-vpa
```

### Watching recommendations arrive

Initially:

```
CPU and memory statistics not received by the VPA object yet
```

Within ~20–30 seconds, `kubectl describe vpa` starts showing:

- **Lower Bound** → minimum recommended request (e.g., `25m` CPU / `262Mi` memory).
- **Target** → what VPA will actually set (e.g., `25m` CPU / `260Mi` memory).
- **Upper Bound** → maximum the app could conceivably need (often very high — take with a pinch of salt).

### VPA in action (Auto mode)

- In `kubectl describe vpa`, events appear:
  ```
  Evicted pod nginx-deploy-xxxxx 2 seconds ago from vpa-updater
  Reason: to apply resource recommendations
  ```
- `kubectl get pods` → new pods have replaced the old ones.
- `kubectl describe pod <new-pod>` → requests changed:
  - **Before:** `cpu: 100m`, no memory request.
  - **After:** `cpu: 25m`, memory request set (matching VPA recommendation).

### What VPA changed

- **Decreased** CPU request from `100m` → `25m` (VPA saw the app didn't need 100m).
- **Added** a memory request that wasn't defined before.
- Pods **restarted** automatically (Auto mode).

### Recommended production usage: `Off` mode

The lecturer's real-world preference:

- Run VPA in **Off mode** in production.
- VPA only **recommends**, doesn't apply or restart.

**Why?**
- Application teams often don't know what requests/limits to set.
- Deploy the app with VPA **Off** → wait for recommendations → set requests (and take a 20–30% buffer for limits) manually.

**VPA is a learning/recommendation tool as much as an autoscaler.**

### HPA vs VPA — quick comparison

| Aspect | HPA | VPA |
|---|---|---|
| Scales | **Number of pods** | **CPU/memory of pods** |
| Direction | Horizontal (out/in) | Vertical (up/down) |
| Restart needed? | **No** | **Yes** |
| Uses metrics-server? | Yes (CPU/mem); plus custom metrics | Yes (for usage analysis) |
| Recommended for production? | **Always** — every production deployment uses it | Often **Off mode** for tuning |
| Best use case | Handle variable traffic | Right-size new applications |

---

## Key Takeaways

1. **Scaling** = matching resources to demand. Horizontal (more pods) vs Vertical (bigger pods).
2. **Horizontal** uses **HPA**; **Vertical** uses **VPA**.
3. **HPA** is a control loop that queries **metrics-server** every **15 seconds** and scales **deployments / statefulsets**.
4. **HPA supports custom metrics** via `custom.metrics.k8s.io` and `external.metrics.k8s.io` (Prometheus Adapter is common).
5. **VPA** has three components: **Recommender**, **Updater**, **Admission Controller**.
6. **VPA modes:** `Off` (recommend only), `Initial` (set at creation), `Auto` (continuous, restarts pods).
7. **VPA respects PodDisruptionBudgets** when evicting pods.
8. **Nodes** are horizontally scaled with **Cluster Autoscaler** or **Karpenter**; vertical node scaling is **not used** in production.
9. **Node groups** (per configuration) + cluster-autoscaler/Karpenter = standard production pattern.
10. **Exam (CKA 1.32):** syllabus says “Configure workload autoscaling” — know **both HPA and VPA**.

---

## Essential Commands

```bash
# HPA
kubectl autoscale deployment <name> --min=1 --max=5 --cpu-percent=50
kubectl get hpa
kubectl describe hpa <name>
kubectl delete hpa <name>

# VPA (installed via autoscaler repo)
kubectl get vpa
kubectl describe vpa <name>

# Metrics
kubectl top nodes
kubectl top pods
kubectl events

# Load generation (busybox)
kubectl run load-gen --image=busybox --rm -it -- /bin/sh -c \
  "while true; do wget -q -O- http://<service>; done"
```

---

## What's Next (Day 21)

- **Multi-container pod patterns** (sidecar, adapter, ambassador, init containers, etc.).

---

*End of Day 20 notes.*