# DaemonSets, Jobs & CronJobs — Incremental Learning Notes (Day 29)

> Source: Day 29 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: The three workload types that are **not** Deployments — **DaemonSet** (one pod per node), **Job** (run to completion), **CronJob** (run on a schedule).
> How to use: one chunk at a time. Answer the recall questions **before** moving on. Do the practice task — that's where the learning actually sticks.
> Exam note: the instructor states plainly that **Jobs and CronJobs are not in the CKA curriculum** (they're CKAD territory). They are still everywhere in production, so they're worth the hour.

---

## 1) Incremental Learning Prompt (Copy/Paste)

```text
Act as my incremental Kubernetes tutor for a CKA course.

Source material: Day 29 lecture on Kubernetes workloads — DaemonSets (one pod per node,
tolerations for the control plane, infrastructure agents), Jobs (completions, parallelism,
backoffLimit, ttlSecondsAfterFinished, restartPolicy), and CronJobs (cron expressions,
job templates, cleanup, jobs piling up).

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

Topic: DaemonSets, Jobs and CronJobs from Day 29 of a CKA course.
```

---

## 2) Progress Tracker

- [ ] Chunk 1: The problem — Deployments don't guarantee one pod per node
- [ ] Chunk 2: What a DaemonSet is, and when you need one
- [ ] Chunk 3: Does a DaemonSet run on the control plane?
- [ ] Chunk 4: DaemonSets in a live cluster (kube-proxy)
- [ ] Chunk 5: DaemonSet YAML anatomy
- [ ] Chunk 6: The DaemonSet demo (namespace, context, delete-ns caution)
- [ ] Chunk 7: Jobs — tasks that start, finish, and exit
- [ ] Chunk 8: Job YAML — TTL, restartPolicy, and why `Always` is illegal
- [ ] Chunk 9: `completions` vs `parallelism`
- [ ] Chunk 10: `backoffLimit` vs `restartPolicy` — two different retry mechanisms
- [ ] Chunk 11: The Job demo — watching it complete and self-clean
- [ ] Chunk 12: CronJobs and cron expressions
- [ ] Chunk 13: The CronJob demo — and what happens without TTL
- [ ] Chunk 14: Choosing between Deployment, DaemonSet, Job, CronJob

---

## Chunk 1: The problem — Deployments don't guarantee one pod per node

**Learning goal:** Understand exactly what a DaemonSet adds that a Deployment cannot.

### The cluster on screen

```
Control plane node  ← TAINTED (effect: NoSchedule)
worker-1
worker-2
worker-3
```

A Deployment requests **2 replicas**. No tolerations are specified.

### What the scheduler does

From **Day 15**, the scheduler checks, before it assigns `nodeName`:

1. **Resource availability**
2. **Taints and tolerations**
3. **Affinity / anti-affinity rules**

Because the control-plane node is tainted with `NoSchedule` and our pods have no matching toleration, the two pods can only go to worker-1/2/3. In the lecture's run, the scheduler picks **worker-1** and **worker-2** — one each.

### The sentence that matters

> **The scheduler does not guarantee equal distribution.**

If worker-2 and worker-3 were under resource pressure, or node affinity/taints applied, **both pods could land on the same node**. Perfectly legal — Kubernetes promises the *number* of pods, not *where* they run.

And for a Deployment, **we don't care**. That's the point of a Deployment: *"keep N pods running somewhere; you decide where."*

### The question that creates DaemonSets

> *"What if I want exactly one pod on **every** node?"*

With 3 worker nodes you'd want 3 pods — one per node. And if you *also* wanted the control plane covered, 4.

That's not a replicas count. That's a **relationship between pods and nodes** — and replicas can't express it.

### The analogy

| | Deployment | DaemonSet |
|---|---|---|
| Think of it as | *"I need 3 cashiers"* | *"Every checkout lane needs one cashier"* |
| Add a new lane | 3 cashiers still, maybe 2 lanes doubled up | **A 4th cashier appears automatically** |

One is a headcount. The other is a coverage guarantee.

### Key takeaway

> A Deployment guarantees **how many** pods exist. A DaemonSet guarantees **where** — one per node.

### Active recall

1. Name the three scheduler considerations from Day 15.
2. In the lecture's example, why couldn't the pods land on the control plane?
3. Could both Deployment pods land on a single node? What does that prove about Deployments?

### Practice task

Your cluster has 5 worker nodes and 1 control plane node. A Deployment has `replicas: 3` and no anti-affinity. Write down every possible node distribution, then explain why the scheduler might legally put all three on one node.

---

## Chunk 2: What a DaemonSet is, and when you need one

**Learning goal:** State the definition precisely and name the real use cases.

### Definition

> **A DaemonSet ensures that one pod runs on every available node.**
> It **automatically manages pod creation/deletion as nodes are added and removed.**

Two halves, both essential:

- **Coverage** — one pod per node, always.
- **Automatic scaling with the cluster** — add a node, a pod appears; remove a node, its pod goes.

No `replicas` field. You never say "3." You say "everywhere," and Kubernetes derives 3 from the cluster size.

### Why would you want a pod on every node?

Because some software's **job is to serve the node itself** — not to serve user traffic.

| Use case | Why every node |
|---|---|
| **Logging agent** | Collect logs from **each node and its pods** |
| **Monitoring agent** | Metrics from every node's workloads |
| **Security agent** | Runtime/sensor coverage on all hosts |
| **`kube-proxy`** | It is the **traffic director** — see Chunk 4 |
| **CNI plugin** (Calico, Flannel, AWS VPC CNI, Azure CNI) | Networking must exist on every node |
| **CSI plugin** (EBS CSI, EFS CSI) | Storage must be attachable from every node |

> The unifying idea: **infrastructure components are per-node by nature.** Their whole purpose is local coverage.

### The clean distinction

```
Deployment  → an application that should run on SOME nodes (N replicas)
DaemonSet   → infrastructure that must run on EVERY node (one per node)
Job         → a task that should run ONCE and stop
CronJob     → a task that should run ONCE per schedule
```

### Key takeaway

> DaemonSet = **one pod per node, auto-managed** as the cluster grows and shrinks. It's the natural shape for **infrastructure agents**.

### Active recall

1. Why does a DaemonSet have no `replicas` field?
2. Give four real DaemonSet workloads and one sentence each on why they need every node.
3. What happens to DaemonSet pods when you add a node? When you delete one?

### Practice task

Classify each as Deployment or DaemonSet, with a one-line reason: nginx frontend, Fluent Bit log shipper, Calico node agent, payment API, Prometheus node-exporter, dashboard UI.

---

## Chunk 3: Does a DaemonSet run on the control plane?

**Learning goal:** Connect taints/tolerations to DaemonSet placement — the "it depends" answer.

### First: the mechanism

DaemonSet pods are **pods**, scheduled by the **same rules**. If the control-plane node is **tainted**, a DaemonSet pod lands there **only if it has a matching toleration**.

The course's control-plane node carries:

```
Taint: node-role.kubernetes.io/control-plane:NoSchedule
```

So by default, a DaemonSet covers **worker nodes only**.

### How kube-proxy gets everywhere — the catch-all toleration

```yaml
spec:
  template:
    spec:
      tolerations:
        - operator: Exists
```

> **`operator: Exists` with no key and no value = "I tolerate everything."**

Read it literally: *don't care what the key is, don't care what the value is, don't even care what the effect is.* Any taint is tolerated.

That's why `kube-proxy` runs on the control-plane node too. A catch-all toleration is powerful and dangerous — use it only when the workload genuinely must run everywhere.

### The "it depends" part — managed vs self-managed

| Cluster type | What happens to *your* DaemonSets |
|---|---|
| **Managed** (EKS, AKS, GKE) | The cloud provider **owns and governs the control plane**. Your logging/monitoring/security DaemonSets run on **worker nodes only** — you don't get agents on a control plane you don't administer |
| **Self-managed** | **Your call.** If you want coverage on the control plane, **add the matching toleration** |

The lecture's demo DaemonSet **includes the toleration**, so it runs on the control-plane node too — which is why the desired count equals the **total** node count rather than worker count.

### Key takeaway

> A DaemonSet runs on the control plane **only with a matching toleration**. Managed clusters generally keep your agents off a control plane you don't own.

### Active recall

1. What exactly does `operator: Exists` tolerate?
2. Why does `kube-proxy` appear on the control-plane node?
3. On EKS, should you expect your Fluent Bit DaemonSet on the control-plane node? Why not?

### Practice task

Write the toleration block for a DaemonSet that must tolerate the specific taint `node-role.kubernetes.io/control-plane:NoSchedule` (key + effect, no value), and then write the catch-all version. What's the risk difference?

---

## Chunk 4: DaemonSets in a live cluster (kube-proxy)

**Learning goal:** Read DaemonSet state from the cluster and understand `DESIRED = node count`.

### Why kube-proxy is the perfect case study

From **Day 07**, every node runs `kube-proxy`, and it does **Service-to-Pod networking**:

1. **Chooses which pod serves** a request (load balancing across Service endpoints).
2. **Forwards only to healthy pods** — if node 2 has a problem, traffic goes to healthy pods elsewhere.
3. **Rewrites the destination** — the frontend sends to the Service's **DNS name** (resolved by **CoreDNS** to the Service IP); kube-proxy **changes the destination IP** to the chosen pod's IP.

> kube-proxy is the **traffic director**. If it's missing on a node, that node's pods can't properly use Services. Hence: every node.

### Reading it

```bash
kubectl get ds -n kube-system
```

```
NAME         DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR   AGE
kube-proxy   3         3         3       3            3           ...             40d
```

**`DESIRED = 3`** because:

```bash
kubectl get nodes
# 3 nodes
```

> One pod per node ⇒ desired == node count. Add a 4th node and desired becomes 4 **automatically**.

### Seeing one pod per node

```bash
kubectl get pods -n kube-system -o wide
```

`-o wide` is the key flag — it adds the **`NODE`** column, which is how you *prove* the one-per-node property rather than assuming it.

```
kube-proxy-abcde   1/1   Running   ...   kind-control-plane
kube-proxy-fghij   1/1   Running   ...   kind-worker
kube-proxy-klmno   1/1   Running   ...   kind-worker2
```

> Three nodes, three kube-proxy pods, **one per node** — including the control plane, thanks to the catch-all toleration (Chunk 3).

### Confirming the toleration in the live object

```bash
kubectl get ds kube-proxy -n kube-system -o yaml
```

```yaml
      tolerations:
        - operator: Exists
```

There it is — the reason it runs on the tainted control-plane node.

### Key takeaway

> **`DESIRED == number of nodes`** is the DaemonSet signature. Use `-o wide` to see the `NODE` column and verify the one-per-node property.

### Active recall

1. Why is `DESIRED` 3 rather than a number someone typed?
2. Which flag reveals which node each pod is on?
3. Explain kube-proxy's role in one sentence, and why it justifies a DaemonSet.

### Practice task

Run `kubectl get ds -n kube-system` and `kubectl get nodes` on your cluster. Does `DESIRED` equal the node count? Now check `kubectl get ds -n kube-system kube-proxy -o yaml | Select-String -Pattern tolerations -Context 0,3` and identify the toleration.

---

## Chunk 5: DaemonSet YAML anatomy

**Learning goal:** Write a DaemonSet from memory and know what each block does.

### First, confirm the object exists and its API group

```bash
kubectl api-resources | Select-String daemonset
```

```
daemonsets    ds    apps/v1    true    DaemonSet
```

- Short name **`ds`**
- API group **`apps/v1`**
- **Namespaced: true**
- Kind is **`DaemonSet`** — capital D, capital S. (`kubectl get ds` is fine; the manifest is case-sensitive.)

### The manifest

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: log-collector
  namespace: logging-ns          # infrastructure gets its OWN namespace
spec:
  selector:
    matchLabels:
      app: log-collector         # must match the template labels
  template:
    metadata:
      labels:
        app: log-collector
    spec:
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          effect: NoSchedule    # so it also runs on the control plane
      containers:
        - name: log-collector
          image: busybox
          command: ["sh", "-c", "echo collecting logs; sleep 30"]
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits:   { cpu: 100m, memory: 128Mi }
          volumeMounts:
            - name: host-logs
              mountPath: /var/log
              readOnly: true
      volumes:
        - name: host-logs
          hostPath:
            path: /var/log        # simulate reading NODE logs
```

### The pieces worth naming

| Block | Why it's there |
|---|---|
| **`namespace`** | Infra components live in their **own namespace** (see below) |
| **`selector.matchLabels`** | Must match the pod template — the DaemonSet only manages pods it owns |
| **`template`** | The pod spec — identical shape to a Deployment's |
| **`tolerations`** | To reach the tainted control-plane node |
| **resources** | Day 19: agents starve neighbours if unbounded |
| **`hostPath` volume** | Simulates access to **node logs** |

### Why the separate namespace?

This is a naming/ops principle worth internalising (Day 14 callback):

> **Segregate by department, project, or environment — and for infrastructure, by function.**

Benefits called out in the lecture:

- **Tidy cluster** — logs live with logging, security with security.
- **Clean removal** — delete the namespace and *everything* namespaced in it goes: Deployments, Roles, ServiceAccounts, NetworkPolicies, the lot.
- **Tool replacement** — swapping from one security tool to another means **deleting one namespace** and deploying into a new one, with no residue.

System components already do this: `kube-proxy` lives in **`kube-system`**, the namespace for system-level components.

### The `hostPath` note (honest about simulation)

> Real log shipping doesn't curl up inside the pod. Logs are typically **shipped to central storage** — EFS, S3, Google Cloud Storage, Azure Blobs — or **streamed to** Elasticsearch, Loki, or a cloud service like **CloudWatch Logs**.

`hostPath` here just demonstrates "the pod can read the node's log directory" (Day 27: `hostPath` is intended for this kind of node-local access, with security caveats).

### Key takeaway

> A DaemonSet is a **pod template + selector**, with **no replicas** — plus tolerations if it must reach tainted nodes.

### Active recall

1. Which field does a DaemonSet replace in the Deployment mental model?
2. Why must `selector.matchLabels` match the template's labels?
3. Give two operational reasons infrastructure gets its own namespace.

### Practice task

Write the `tolerations` block for a DaemonSet that must run **everywhere** including a control plane with `node-role.kubernetes.io/control-plane:NoSchedule`. Then explain how you'd verify placement.

---

## Chunk 6: The DaemonSet demo — namespace, context, and a deletion warning

**Learning goal:** Learn the operational gotchas that cost real time: missing namespace, wrong context namespace, and `delete ns`.

### Gotcha 1 — a missing namespace is a hard error

```bash
kubectl apply -f ds.yaml
# Error from server (NotFound): namespaces "logging-ns" not found
```

> **`kubectl apply` does not create the namespace for you.**

Fix:

```bash
kubectl create ns logging-ns
kubectl apply -f ds.yaml
# daemonset.apps/log-collector created
```

### Gotcha 2 — "I applied it but `kubectl get pods` shows nothing"

Because your context points at a **namespace**, and the DaemonSet lives in another one.

```bash
kubectl config get-contexts        # which context, cluster, user, namespace?
```

Switch the **current context's** namespace:

```bash
kubectl config set-context --current --namespace=logging-ns
kubectl get pods                   # now you see them
```

> This is the single most common "where did my object go?" moment in Kubernetes. Nothing is broken — you're just looking in the wrong room.

### What you see

```bash
kubectl get pods
# log-collector-xxxxx   1/1   Running   0   40s
# log-collector-yyyyy   1/1   Running   0   ...    ← three pods
# log-collector-zzzzz   1/1   Running   0   ...
```

```bash
kubectl get pods -o wide
# ... NODE column shows one pod per node, INCLUDING the control plane
```

Because the DaemonSet carries the toleration (Chunk 3).

### No count anywhere in the YAML

> You will **not** find `replicas` in a DaemonSet manifest. The count **is** the node count.

```bash
kubectl get ds
kubectl describe ds log-collector
```

### Gotcha 3 — `delete namespace` is a sledgehammer

```bash
kubectl delete ns logging-ns
```

That deletes **everything inside it** — every namespaced object belonging to that logical unit.

> The instructor's own warning: *"Be extra careful… this will take away the soul of that namespace… I have committed this mistake in the past. We all have been guilty."*

**Why it's usually the right tool for infra namespaces** (Chunk 5 — clean tool replacement), and **why you should still pause before typing it**.

### Gotcha 4 — the context now points at a namespace that no longer exists

After deletion:

```bash
kubectl get pods
# No resources found ... (or odd behaviour)
kubectl config get-contexts     # namespace still logging-ns!
```

Fix it back:

```bash
kubectl config set-context --current --namespace=default
```

> **Deleting a namespace does not reset your context.** Remember this one.

### Key takeaway

> Namespace, then context, then apply. And note that **`delete ns` removes everything** while **your context keeps pointing at the dead namespace**.

### Active recall

1. Does `kubectl apply` create a missing namespace? What do you do instead?
2. You applied a DaemonSet but `kubectl get pods` is empty in `default`. What's the likely cause?
3. After `kubectl delete ns logging-ns`, what still needs fixing — and why?

### Practice task

Write the four-command sequence to go from "fresh cluster" to "seeing my DaemonSet pods on every node," including the namespace creation and the context switch.

---

## Chunk 7: Jobs — tasks that start, finish, and exit

**Learning goal:** Know what a Job is for, and why a Deployment is the wrong tool for it.

### Definition

> **A Job runs one-off tasks that start, complete, and exit.**

A Deployment is for things that should run **24×7**: web servers, API gateways. A Job is for work with an **end**.

### The comparison that makes it click

| | Deployment | Job |
|---|---|---|
| Lifetime | **Forever** (desired replicas always up) | **Until completion** |
| `nginx` / API gateway | ✅ appropriate | ❌ wrong |
| `ping 4.4.4.4` once | ❌ it would restart forever | ✅ correct |
| Typical restart policy | `Always` | `OnFailure` / `Never` |

> Remember Day 22: a Deployments' `Always` policy means a container that **completes successfully** still gets restarted — which is why one-shot work under a Deployment degenerates into `CrashLoopBackOff`.

### Use cases

| Use case | Why a Job |
|---|---|
| **Copy a file** A → B | One-off, then done |
| **Delete temporary files** | Cleanup work |
| **Database migrations** | Run once, in order, with retries |
| **Backups** | Discrete unit of work |
| **One-time reports / analysis** | Produce output, exit |

### "One or more pods"

> A Job **creates one or more pods** to run the task to completion.

Why more than one? Example: copying **gigabytes**. One pod can't saturate; you split the work — pod 1 takes the first 5 GB, pod 2 the next 5 GB. That's the `completions` field (Chunk 9).

### Retries

> **Retries automatically if a pod fails, based on the backoff policy.**

That's `backoffLimit` (Chunk 10). It's also what makes Jobs safe for migrations: transient failure → retry, real failure → eventually marked failed.

### Where the object lives

```bash
kubectl api-resources | Select-String job
# cronjobs   cj   batch/v1   true   CronJob
# jobs       ...  batch/v1   true   Job
```

- API group **`batch/v1`** — not `apps/v1`
- **Namespaced**
- Part of **Workload Management** in the Kubernetes docs, alongside Deployments, DaemonSets, StatefulSets (later)

### Key takeaway

> A Job is for work with a **finish line**. `batch/v1`, namespaced, one-or-more pods, retried on failure.

### Active recall

1. What distinguishes a Job use case from a Deployment use case?
2. Why would a Job ever need more than one pod?
3. Which API group do Jobs belong to, and why does that matter for the manifest?

### Practice task

Classify: a nightly DB migration, an nginx server, a one-time data export, a REST API, "copy this 20 GB archive." Which are Jobs, and which Jobs would you give more than one pod?

---

## Chunk 8: Job YAML — TTL, restartPolicy, and why `Always` is illegal

**Learning goal:** Read a Job manifest and understand the two fields people get wrong.

### The manifest

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: hello-job
spec:
  ttlSecondsAfterFinished: 60      # clean up 60s after completion
  completions: 2                   # 2 successful pod completions needed
  parallelism: 2                   # run 2 at a time
  backoffLimit: 4                  # recreate the pod up to 4 times on failure
  template:
    spec:
      restartPolicy: OnFailure     # OnFailure | Never — NOT Always
      containers:
        - name: hello
          image: busybox
          command: ["sh", "-c", "echo 'Hello from the job'; sleep 10"]
```

### `ttlSecondsAfterFinished` — cluster hygiene

> When the Job completes (**succeeded or failed**), **remove it and its pods after 60 seconds**.

Without it, hundreds of finished Jobs leave hundreds of `Completed` pods cluttering `kubectl get pods`.

**The obvious objection:** *"If it failed, wouldn't I want the pod to troubleshoot?"*

**The answer:** in production you already have a **logging agent running as a DaemonSet**, shipping logs to central storage (Chunk 2 and 5 tie together here). The logs outlive the pod, so deleting the pod costs you nothing.

> If you do **not** have a logging agent yet — **build one first**, then add the TTL.

### `restartPolicy` — only two legal values

| Value | Meaning | Legal for a Job? |
|---|---|---|
| **`OnFailure`** | restart the **container** if it exits non-zero | ✅ |
| **`Never`** | never restart the container | ✅ |
| **`Always`** | restart regardless of exit code | ❌ **rejected** |

**Why is `Always` illegal here?** Because it contradicts the entire purpose: a Job wants the container to **finish and stay finished**. `Always` would restart even a successful exit — the Day 22 `CrashLoopBackOff` trap.

### The two retry knobs are not the same thing

| Knob | Who acts | What happens |
|---|---|---|
| **`restartPolicy`** | **kubelet** | **Restarts the container inside the pod** |
| **`backoffLimit`** | **Job controller** | **Recreates the whole pod** |

This distinction is the crux of Chunk 10 — but note it here: *"the backoff limit will recreate the pod… it will not be restarting the container inside the pod."*

### Key takeaway

> `ttlSecondsAfterFinished` cleans up; `restartPolicy` must be `OnFailure` or `Never`; and `Always` is invalid for Jobs.

### Active recall

1. What does `ttlSecondsAfterFinished: 60` delete, and when?
2. Which restart policies are legal for a Job, and why is `Always` not?
3. Who restarts a container — and who recreates a pod?

### Practice task

Write the Job manifest for "print the date, then exit" with: 3 completions, 1 parallelism, at most 2 retries, and cleanup 30 seconds after finishing. Then state how many pods will exist at any moment.

---

## Chunk 9: `completions` vs `parallelism`

**Learning goal:** Never confuse these two again — and be able to compute the wave pattern.

### Definitions

| Field | Question it answers |
|---|---|
| **`completions: N`** | **How many pods must succeed** before the Job is successful? |
| **`parallelism: P`** | **How many pods may run at the same time?** |

- **`completions`** = total work units (pod-sized).
- **`parallelism`** = concurrency limit.

### Success and failure at the Job level

With `completions: 2`:

> Both pods must **complete successfully** for the Job to be **Successful**. If **one** fails, the **Job** is marked **Failed** (subject to `backoffLimit` retries).

That's why the Job's `describe` reports *"Pods Statuses: 2 Succeeded"* — the Job aggregates pods.

### The wave math (the exam-style question)

| `completions` | `parallelism` | Behaviour |
|---|---|---|
| 2 | 2 | **Both at once**, one wave |
| 10 | 5 | **5 pods**, wait; then **5 more** → **2 waves** |
| 10 | 1 | **One at a time**, sequentially — 10 waves |
| 5 | 3 | 3, then 2 |

> General rule: **number of waves = ⌈completions ÷ parallelism⌉**.

### Why would you limit parallelism?

Because "run 10 at once" can hammer a database, exhaust node resources, or saturate network. `parallelism` is the throttle; `completions` is the work order.

### Why multiple pods at all?

Load distribution — the 10 GB copy split across pods. Same logic as replicas in a Deployment, but for **finite** work: you need *N* units of throughput until the task is done, then nothing.

### Key takeaway

> **`completions` = how many must succeed. `parallelism` = how many run at once.** Waves = ⌈completions ÷ parallelism⌉.

### Active recall

1. With `completions: 10` and `parallelism: 5`, how many pods exist in total and in how many waves?
2. Which field makes pods run **sequentially**?
3. Does `parallelism` affect whether the Job is considered successful?

### Practice task

You must process 100 files, and the downstream API allows only 4 concurrent uploads. Write the `completions` and `parallelism` values and compute the number of waves. Then say what you'd change if the API raised its limit to 20.

---

## Chunk 10: `backoffLimit` vs `restartPolicy` — two different retry mechanisms

**Learning goal:** Distinguish the kubelet's container restart from the Job controller's pod recreation.

### The two layers

```
┌─────────────────────────────────────────────┐
│ Job controller (in Controller Manager)      │
│   backoffLimit = 4                          │
│   → pod fails → DELETE pod → CREATE new pod │
├─────────────────────────────────────────────┤
│ kubelet (on the node)                       │
│   restartPolicy = OnFailure / Never         │
│   → container fails → restart in place      │
└─────────────────────────────────────────────┘
```

### `restartPolicy` — the kubelet's tool

> **Restart policy is governed by the kubelet.** With `Always` or `OnFailure`, the kubelet restarts **the container** when it fails. The pod object stays the same; the `RESTARTS` counter on that pod increments.

### `backoffLimit` — the Job controller's tool

> **The Job controller recreates the entire pod.**

- Default in the manifest here: **`backoffLimit: 4`** → up to **4 retries** with a **new pod** each time.
- If it fails the 5th time → the **Job is deemed failed**.
- `describe job` then shows `Failed` with the retry count in the events.

**The wording matters:** *"It will recreate the pod. I'm not talking about containers here… a new pod will be created."*

### Where the Job controller lives

From **Day 07**: the **Controller Manager** is an umbrella term for many controllers. There's a controller per major object type — including a **Job controller** — whose job is to make **desired state match current state**. For a Job, desired state is "N successful completions"; the Job controller keeps creating pods until that's true or `backoffLimit` is exhausted.

### Practical consequences

| Observation | Meaning |
|---|---|
| One pod, `RESTARTS: 4` | `restartPolicy: OnFailure` — kubelet restarted the **container** |
| Five pods, each `Failed` | `backoffLimit` — the **Job controller** recreated pods |
| Job status `Failed` | `backoffLimit` exhausted — give up, and inspect logs |

### Key takeaway

> **`restartPolicy` → kubelet restarts the container. `backoffLimit` → Job controller recreates the pod.** Different actors, different evidence.

### Active recall

1. Which component implements `backoffLimit`?
2. With `backoffLimit: 4`, how many total attempts does a failing pod get?
3. You see one pod with `RESTARTS: 4` and no new pods. Which mechanism is working?

### Practice task

A Job with `restartPolicy: Never` and `backoffLimit: 3` fails repeatedly. Sketch what `kubectl get pods` shows over time (how many pods, what statuses), and what `kubectl describe job` reports at the end.

---

## Chunk 11: The Job demo — watching it complete and self-clean

**Learning goal:** Read Job progress from the cluster: `COMPLETIONS`, pod phases, and TTL cleanup.

### Apply and watch

```bash
kubectl apply -f job.yaml
# job.batch/hello-job created

kubectl get job
# NAME        COMPLETIONS   DURATION   AGE
# hello-job   0/2           3s         3s        ← 0 of 2 done, no pods yet
```

Then, as the controller works:

```bash
kubectl get job      # 1/2 ...   ← one pod created
kubectl get job      # 2/2 ...
```

> **`COMPLETIONS 0/2 → 2/2`** is the Job's progress bar, directly reflecting `completions: 2`.

### Two pods appear at once

```bash
kubectl get pods
# hello-job-abcde   0/1   Completed   0   12s
# hello-job-fghij   0/1   Completed   0   12s
```

Two pods, simultaneously — because **`parallelism: 2`**.

**Why `0/1` and `Completed`?** The `READY` column is `0/1` because a completed container is **not ready** — it's not running, it's done. `Completed` means **exit code 0** (Day 22: `Succeeded` phase, shown as `Completed`).

> `0/1 Completed` is the *correct* and *healthy* state for a finished Job pod. Don't read it as an error.

### Watch the lifecycle live

```bash
kubectl apply -f job.yaml
kubectl get pods -w
```

```
hello-job-xxxxx   0/1   ContainerCreating
hello-job-xxxxx   1/1   Running          ← the 10s sleep
hello-job-xxxxx   0/1   Completed        ← after ~10s
```

`-w` (watch) is how you *see* the transition instead of inferring it.

### The Job's own report

```bash
kubectl describe job hello-job
```

```
Status:         Succeeded
Pods Statuses:  2 Succeeded / 0 Failed
Events:         SuccessfulCreate ...
```

`Pods Statuses: 2 Succeeded` — the Job's aggregate view of its pods.

### Self-cleanup at 60 seconds

```bash
kubectl get pods
# No resources found in default namespace.
```

> `ttlSecondsAfterFinished: 60` removes the Job and its pods from etcd after 60 seconds post-completion.

**Why it's a feature:** without it, every experiment leaves `Completed` pods behind, and `kubectl get pods` becomes unreadable. **Clean cluster, clear signals.**

### Cleanup by hand (when you don't want to wait)

```bash
kubectl delete job hello-job
```

Deleting a Job **cascades** to its pods (owner references), so you don't have to chase them.

### Key takeaway

> `COMPLETIONS n/N` tracks progress; finished pods read `0/1 Completed`; TTL removes them; deleting the Job cascades.

### Active recall

1. What does `COMPLETIONS 0/2` mean, and which field controls the denominator?
2. Why is a completed Job pod shown as `0/1` rather than `1/1`?
3. What removes the pods after completion, and what happens if you `kubectl delete job` instead?

### Practice task

Apply a Job with `completions: 3`, `parallelism: 1`, `ttlSecondsAfterFinished: 30`, then predict—before running it—how many pods you'll see at once, what their phases are, and when `get pods` returns nothing.

---

## Chunk 12: CronJobs and cron expressions

**Learning goal:** Understand the CronJob → Job → Pod chain, and read a cron schedule.

### Definition

> **A CronJob runs Jobs on a scheduled basis, like Linux cron.**

### What plain Linux cron is

A way to tell a system *"run this task at this time"*:

- take a backup at **2:00 a.m.**
- send this email at **5:00 p.m. on 15 January**

### The five-field cron format

```
┌──────── minute        (0–59)
│ ┌────── hour          (0–23)
│ │ ┌──── day of month  (1–31)
│ │ │ ┌── month         (1–12)
│ │ │ │ ┌ day of week   (0–6, Sunday = 0)
│ │ │ │ │
* * * * *
```

Examples from the notes:

| Expression | Meaning |
|---|---|
| `* * * * *` | **every minute** |
| `*/5 * * * *` | every 5 minutes |
| `0 * * * *` | hourly, at minute 0 — hourly DB backup / report |
| `0 2 * * *` | daily at 02:00 |

> **`*/1` is the same as `*`** for "every minute."

### Always verify your expression

Use **crontab.guru** (or similar). A wrong expression silently runs at the wrong time — the worst kind of bug, because nothing errors.

> The instructor's advice: *verify before you ship.*

### The object chain (the key mental model)

```
CronJob  ──(schedule reached)──►  Job  ──►  Pod(s)
   │                               │
   └── has jobTemplate ────────────┘  (the same spec as a standalone Job)
```

> **A CronJob creates a Job; the Job creates pods.** The CronJob does **not** create pods directly.

That's why the fields are nested: `spec.jobTemplate.spec.template.spec.containers` — CronJob → Job → Pod → container.

### The manifest, side by side with a Job

```yaml
# Job                              # CronJob
apiVersion: batch/v1               apiVersion: batch/v1
kind: Job                          kind: CronJob
spec:                              spec:
  completions: 2                     schedule: "* * * * *"     # NEW
  parallelism: 2                     jobTemplate:
  backoffLimit: 4                      spec:
  ttlSecondsAfterFinished: 60            completions: 2        # ← same as before
  template:                              parallelism: 2
    spec:                                backoffLimit: 4
      restartPolicy: OnFailure            ttlSecondsAfterFinished: 60
      containers: [...]                   template:
                                            spec:
                                              restartPolicy: OnFailure
                                              containers: [...]
```

> **Everything below `jobTemplate.spec` is exactly a Job spec.** A CronJob is a Job plus a schedule — that's the whole idea.

### Key takeaway

> CronJob = **schedule + jobTemplate**. The schedule creates **Jobs**, and Jobs create **pods**.

### Active recall

1. Name the five cron fields in order.
2. Which object does the CronJob controller create — pods or Jobs?
3. What is `jobTemplate.spec` structurally identical to?

### Practice task

Write the schedule strings for: every 15 minutes; every day at 03:30; every Monday at midnight; the first day of each month at noon. Then verify one of them at crontab.guru (mentally describe what it should say).

---

## Chunk 13: The CronJob demo — and what happens without TTL

**Learning goal:** Observe scheduled execution, name-prefixing, and the pile-up problem.

### Apply

```bash
kubectl apply -f cronjob.yaml
kubectl get cj          # cj = cronjob
```

```
NAME        SCHEDULE      SUSPEND   ACTIVE   LAST SCHEDULE   AGE
hello-cj    * * * * *     False     0        <none>          5s
```

- Short name **`cj`**.
- `LAST SCHEDULE: <none>` — nothing has fired yet.

### Nothing happens for up to 60 seconds

```bash
kubectl get pods
# No resources found.
```

**Correct.** The schedule is `* * * * *` — the first run happens at the **next minute boundary**. This is where learners think they broke something.

> Rule of thumb: a `* * * * *` CronJob can take up to **59 seconds** to do anything visible.

### After the minute ticks

```bash
kubectl get pods
# hello-cj-28934567-abcde   0/1   Running
# hello-cj-28934567-fghij   0/1   Running
```

**Two pods** — because the `jobTemplate` has `completions: 2` and `parallelism: 2`.

Then, ~10 seconds later (the sleep):

```bash
kubectl get pods
# ... 0/1 Completed
```

### The Job that appeared underneath

```bash
kubectl get jobs
# hello-cj-28934567   2/2   10s   45s
```

> **The Job's name starts with the CronJob's name** — `hello-cj-<timestamp>`. That prefix is how you connect the dots in a busy cluster: *"which CronJob created this Job?"*

```bash
kubectl get cj
# hello-cj ... ACTIVE 0, LAST SCHEDULE 40s
```

The CronJob persists; the Jobs come and go.

### TTL cleanup — Job first, then pods

```bash
# after ttlSecondsAfterFinished: 60
kubectl get jobs
# No resources found.
kubectl get pods
# No resources found.
```

Order matters:

1. **TTL removes the Job object** (60 s after completion).
2. **Garbage collection then removes the pods** — because the Job that owned them is gone.

> That's why pods don't linger even if you never touched them: ownership cascade.

### The pile-up experiment (why TTL matters)

Remove `ttlSecondsAfterFinished` from the CronJob and re-apply. Wait a few minutes:

```bash
kubectl get jobs
# hello-cj-28934567   2/2   40s
# hello-cj-28934568   2/2   100s
# hello-cj-28934569   2/2   160s      ← accumulating, one per minute
kubectl get pods
# ... and their 6 completed pods
```

> Every minute adds a Job and its pods, **forever**. In a "humongous cluster" this becomes unmanageable.

**Conclusion:** for recurring work, **`ttlSecondsAfterFinished` is not optional** — it's what keeps the cluster tidy.

### Key takeaway

> CronJob fires at the next schedule boundary, names Jobs `<cronjob>-<timestamp>`, and **needs TTL** or Jobs pile up indefinitely.

### Active recall

1. Why is `kubectl get pods` empty right after applying a `* * * * *` CronJob?
2. How do you map a Job back to the CronJob that created it?
3. What is the deletion order when TTL fires — Job or pods first, and why?

### Practice task

A CronJob runs hourly with `completions: 1` and no TTL. After 24 hours, how many Jobs and how many pods exist? Now add TTL 60 and re-answer.

---

## Chunk 14: Choosing between Deployment, DaemonSet, Job, CronJob

**Learning goal:** Pick the right workload type instantly — the skill that shows up in design interviews.

### The decision table

| | **Deployment** | **DaemonSet** | **Job** | **CronJob** |
|---|---|---|---|---|
| **Guarantees** | N pods running | **1 pod per node** | Task **completes** | Task runs **per schedule** |
| **Replicas field** | ✅ `replicas` | ❌ none (derived from nodes) | ❌ `completions` instead | ❌ inside `jobTemplate` |
| **Restart policy** | `Always` | `Always` | **`OnFailure` / `Never`** | `OnFailure` / `Never` |
| **Lifetime** | Forever | Forever (node-lifetime) | Until completion | Until completion, repeatedly |
| **API group** | `apps/v1` | `apps/v1` | **`batch/v1`** | **`batch/v1`** |
| **Typical use** | Web servers, APIs, frontends | Logging, monitoring, security, CNI, CSI, kube-proxy | File copy, migration, backup, one-time report | Backups, reports, cleanups, log rotation |
| **Short name** | `deploy` | `ds` | `job` | `cj` |

### The one-sentence rule per type

- **Deployment** — *"keep this running, 24×7."*
- **DaemonSet** — *"one of these on every node, always."*
- **Job** — *"do this once, then stop."*
- **CronJob** — *"do this once, every schedule."*

### Coming next: StatefulSet

The instructor flags the fifth workload controller: **StatefulSets** — covered later. (If you want the preview: stable identity + ordered deployment + per-pod storage — the thing Deployments can't do for databases.)

### Production habits from this lecture

1. **Define requests and limits** on every DaemonSet/Job pod (Day 19) — log agents shouldn't starve applications.
2. **Give infrastructure its own namespace** — clean removal, clean tool swaps.
3. **Use `ttlSecondsAfterFinished`** on Jobs and CronJobs, or your cluster fills with `Completed` pods.
4. **Have a logging agent before you auto-delete pods** — otherwise you delete the evidence.
5. **Verify cron expressions** before shipping — a wrong schedule fails silently.
6. **Tolerate taints deliberately** — `operator: Exists` is a blunt instrument.
7. **Check your context's namespace** before concluding an object "doesn't exist."
8. **Respect `delete ns`** — it is instant, total, and unforgiving.
9. **Watch your work** — `kubectl get pods -w` turns theory into observation.

### Key takeaway

> Four questions, four answers: **continuous? → Deployment. everywhere? → DaemonSet. once? → Job. on a schedule? → CronJob.**

### Active recall

1. Which two workload types use `batch/v1`?
2. Which one has no count field at all, and why?
3. Which restart policy is impossible for a Job, and what does that tell you about its purpose?

### Practice task

For each requirement, name the object type and one key field: (a) nginx with 3 replicas; (b) Fluent Bit on every node; (c) a one-time 20 GB copy using 4 concurrent workers; (d) nightly DB backup at 02:00 with cleanup after 30 seconds; (e) a node-level security sensor.

---

## 15) Recap & Final Check

### One line per chunk

| Chunk | In one line |
|---|---|
| 1 | Deployments promise *count*, not *placement* — the scheduler can stack pods |
| 2 | DaemonSet = one pod **per node**, auto-managed as nodes join/leave |
| 3 | Control-plane coverage needs a **toleration**; `operator: Exists` tolerates all taints |
| 4 | `DESIRED == node count`; `-o wide` proves one-per-node; kube-proxy is the traffic director |
| 5 | DaemonSet YAML = selector + template, **no replicas**; infra gets its own namespace |
| 6 | Create the namespace first; check your context namespace; `delete ns` destroys everything |
| 7 | Job = tasks with a finish line; `batch/v1`; one or more pods; retried on failure |
| 8 | `ttlSecondsAfterFinished` cleans up; `restartPolicy` must be `OnFailure`/`Never` |
| 9 | `completions` = how many succeed; `parallelism` = how many at once |
| 10 | `restartPolicy` → kubelet restarts the container; `backoffLimit` → Job controller recreates the pod |
| 11 | `COMPLETIONS n/N`; finished pods are `0/1 Completed`; TTL then deletes them |
| 12 | CronJob = schedule + jobTemplate; creates **Jobs**, which create pods |
| 13 | Fires at the next boundary; Job names are prefixed; **no TTL = pile-up** |
| 14 | Continuous / everywhere / once / scheduled — four questions, four objects |

### Common pitfalls

- **Expecting a DaemonSet to have `replicas`** — the node count *is* the replica count.
- **Forgetting the toleration** and wondering why the control plane has no pod.
- **`operator: Exists` everywhere** — it tolerates every taint, including ones you didn't intend.
- **`kubectl apply` on a namespaced object without the namespace existing** — hard error.
- **Looking in `default`** while the object sits in another namespace.
- **Thinking `0/1 Completed` is a failure** — it's the success state for a Job pod.
- **Setting `restartPolicy: Always` on a Job** — rejected by the API.
- **Confusing `completions` with `parallelism`** — success count vs concurrency.
- **Forgetting `ttlSecondsAfterFinished`** — `Completed` pods and Jobs accumulate forever.
- **Deleting the namespace to "clean up one thing"** — takes the whole namespace with it, and leaves your context pointing at a corpse.

### Mini exam (no looking back)

1. A DaemonSet runs on 3 of 4 nodes. The 4th is the control plane. What is missing from the manifest?
2. Write the Job spec fields for: 10 completions, 5 parallelism, at most 3 retries, cleanup 120 s after finish.
3. Which component recreates a pod that exceeded `backoffLimit`? What happens when the limit is exhausted?
4. A cron expression is `0 2 * * *`. When does it run, and what object does it create at that moment?
5. After 3 hours, a `* * * * *` CronJob with TTL 60 has how many Job objects? What if TTL is removed?
6. Name the four workload objects and the single question that picks each.

### If you can answer all six, this lecture is done.

---

## What's Next (Day 30)

- **Encryption & TLS** — symmetric vs asymmetric encryption, in-transit vs at-rest, SSH challenge/response, and the TLS handshake (the foundation for the security section).

---

*End of Day 29 incremental notes.*
