# Kubernetes Health Probes — Readiness, Liveness & Startup — Complete Notes (Day 23)

> Source: Day 23 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Health probes — why they exist, the three types, the probe mechanisms, and every timer.
> Numbering note: the instructor labels this lecture **Day 23** (stated at 0:00, and cross-referenced as following Day 22's troubleshooting lecture). It may appear as **video #26** in a playlist that includes extra clips outside the instructor's day count — the day numbering below follows the course, not the playlist.
> Prerequisite: Day 07 (pod internals, kubelet), Day 19 (requests/limits, OOMKilled), Day 21 (`restartPolicy`), Day 22 (pod lifecycle phases, restart business).

---

## 1) Why Do We Need Health Probes?

Three problems, three answers — this is the entire "why" of the lecture.

| Problem | What you want | Solved by |
|---|---|---|
| Unhealthy pods receive traffic | Only **healthy** pods should serve requests | **Readiness** probe |
| App is stuck in a **deadlock** / hung state | Kubernetes should **restart** it | **Liveness** probe |
| App needs a long time to boot | Give pods **enough time to start** | **Startup** probe |

> **The philosophical point:** `kubectl get pods` showing `Running` means the *container process* exists. It does **not** mean the application is healthy, ready, or responsive. Probes are how Kubernetes learns the difference.

---

## 2) Recap — Pod Status Is the Worst Container's Status

This matters because probes change per-container state, and you need to read the pod status correctly.

- A pod with **2 containers** is `Running` **only when all containers are running fine**.
- If **any** container has an error, the **pod status shows that container's error**.

### Live proof (from the demo)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: test
spec:
  containers:
    - name: nginx
      image: nginx
    - name: supporter
      image: gibberish-image-name     # nonsense on purpose
```

```bash
kubectl apply -f test.yaml
kubectl get pods
```

```
NAME                    READY   STATUS         RESTARTS   AGE
test                    1/2     ErrImagePull   0          10s
readiness-probe-demo    1/1     Running        0          3m
```

- `1/2` → only the nginx container is ready; the "supporter" container can't pull its image.
- The **pod** status is `ErrImagePull`, even though one container is perfectly healthy — **worst-container rule** (Day 22).
- The single-container pod next to it shows `Running`, because its only container is fine.

**A container in `ErrImagePull` cannot be probed at all** — and that's the next key rule.

---

## 3) The Fundamental Rule: Probing Starts When the Container Is Running

> **Probes only work once the container is in `Running` state.**

- Makes sense: if the application has never started, there's nothing to check.
- A container stuck in `ErrImagePull` / `ImagePullBackOff` / `ContainerCreating` is **not** being probed.
- For the *pod* to show `Running`, **all** its containers must be running.
- Once a container flips to `Running`, its **readiness/liveness timers begin**, and probing continues for the container's whole life.

### Who actually performs the probe?

> **The kubelet performs the probes.**

- kubelet runs on **every worker node and every control-plane node**.
- It health-checks the containers on **its own node**.
- It **reports pod and node health to the API server**.
- No controller, no sidecar, no agent needed — probes are a **kubelet** feature.

```
you define probe ──► container spec ──► kubelet on that node ──► runs the probe
                                              │
                                              ▼
                                        reports health ──► API server ──► kubectl get pods
```

---

## 4) Readiness Probe

### Definition

> Checks whether the container is **ready to serve traffic**.

| Aspect | Behaviour |
|---|---|
| **On failure** | Pod is marked **`NotReady`** → **removed from load balancing** → receives **no traffic** |
| **Restart?** | **No.** Readiness never restarts a container |
| **Duration** | Monitors the container for its **entire life** — continuously |
| **Effect scope** | **Pod-level**: any one container failing readiness makes the **whole pod** NotReady |

### The readiness counter

In the `READY` column (`1/1`, `2/2`), the first number is how many containers are **ready**:

- Single container, ready → `1/1`
- Two containers, only one ready → `1/2`
- A failed readiness probe changes a `1` to a `0` → status becomes **`NotReady`**

`NotReady` ⇒ **no active traffic**. Kubernetes removes the pod's IP from the Service's endpoints, so the load balancer stops sending requests.

### The multi-container gotcha (critical)

> **If one container fails its readiness probe, NO container in that pod receives traffic** — not even the healthy ones.

Why? Because **readiness is a property of the pod**, not of the individual container. Service endpoints point at **pods**, and a pod is either ready or not.

```
Pod (2 containers)
  ├── container A: readiness PASS
  └── container B: readiness FAIL
        │
        ▼
  Pod = NotReady  →  removed from Service endpoints
        │
        ▼
  traffic to A: ZERO   traffic to B: ZERO
```

This is deliberately conservative: if part of the pod is broken, the whole pod's traffic-handling contract is suspect.

### Use cases

1. **DB connection initialization** — the app isn't ready until its database connection is established.
2. **Application initialization** — caches warm, config loaded, migrations applied.
3. **Temporary overload** — a brief glitch (resource spike, momentary hang). Restarting is **expensive**; you'd rather pull it out of the load balancer for 2–3 seconds and let it recover.

### Why "temporary" is the key word in use case 3

Restarting a pod is **hard** — cold start, connection re-establishment, cache rebuild. You don't want to restart unnecessarily.

Readiness lets you **pause traffic without killing the process**:

```
probe fails → pod NotReady → no traffic
   (wait; problem self-heals)
probe passes → pod Ready → traffic resumes
```

**Readiness = "stop sending me requests for now."** Liveness = "kill and restart me."

> If a file the probe needs becomes inaccessible for 2–3 seconds because of resource over-utilization, readiness just takes the pod out of rotation. No restart, no cold start. That's the point.

---

## 5) Liveness Probe

### Definition

> Checks whether the container is **alive** — and restarts it if it isn't.

| Aspect | Behaviour |
|---|---|
| **On failure** | The **container is restarted** (per `restartPolicy`) |
| **Restart?** | **Yes** — this is the probe's whole purpose |
| **Duration** | Monitors the container for its **entire life** — continuously |
| **Effect scope** | **Container-level**: only the **failing container** is restarted |

### The multi-container contrast (exam favourite)

| | Readiness failure | Liveness failure |
|---|---|---|
| **Who is affected** | The **whole pod** goes NotReady | **Only the failing container** is restarted |
| **Other containers** | Also lose traffic | **Left completely alone** |
| **Restart happens** | Never | Always (subject to policy) |

That is the single most important distinction between readiness and liveness in a multi-container pod.

### Use cases

1. **Deadlock detection** — the process is running but doing nothing; only a restart clears it.
2. **Unresponsive / hung states** — you know it will not recover on its own.
3. **Memory leaks / stuck in out-of-memory** — the app is wedged inside an OOM condition and needs a fresh start (Day 19 covers OOMKilled itself).

### The judgement call

> **"Irrecoverable" is the keyword.** If the app can recover by itself, that's readiness. If it cannot, it's liveness.

Use liveness only for states where **only a restart helps**. An over-eager liveness probe turns a blip into a restart storm (which is what `CrashLoopBackOff` looks like from the outside — see the demo).

---

## 6) Startup Probe

### Definition

> Gives a **slow-starting application** enough time to boot, and **prevents premature restarts** by liveness.

| Aspect | Behaviour |
|---|---|
| **On failure** (past its budget) | The container is **restarted** |
| **Restart?** | **Yes** |
| **Duration** | **Only at start-up.** Once it succeeds, it **never runs again** |
| **Gates the others** | **Readiness and liveness do NOT run until the startup probe succeeds** |

### Why it exists

Without a startup probe, you have a conflict:

- The app needs **2 minutes** to boot.
- Liveness must not wait 2 minutes (then a real hang goes undetected for 2 minutes).
- But if liveness starts after, say, 30 seconds, it **kills the app mid-boot** → `CrashLoopBackOff` forever.

The startup probe resolves this:

```
container starts
   │
   ▼
startup probe runs (generous budget: initialDelay + period × failureThreshold)
   │
   ├── succeeds ──► startup probe STOPS ──► liveness + readiness begin
   │
   └── exhausts budget ──► container restarted, cycle repeats
```

So the slow boot gets a **long grace window**, while steady-state liveness stays **tight**.

### The init container analogy (from the instructor)

- **Init containers** (Day 21): run before the main container, complete their job, then disappear.
- **Startup probes**: run before readiness/liveness matter, complete their job, then disappear.

> Kubernetes named these well — *init* and *startup* both mean "the beginning, and then never again." **Startup probe is to liveness what init container is to the main container.**

### Use case beyond "slow app"

Don't limit yourself to "my app takes 2 minutes":

- The startup probe's command is cloning a dataset that needs at least **1 minute**.
- Give it **1.5 minutes** — the extra buffer is the whole point.
- Same reasoning as `terminationGracePeriodSeconds` having buffer (Day 22).

---

## 7) Probe Mechanisms (How the kubelet Actually Checks)

**These mechanisms are probe-agnostic.** Any of the three can back a readiness, liveness, or startup probe — you pick the one that matches your application.

### 1. `httpGet` — is a path reachable on a port?

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
    httpHeaders:
      - name: Custom-Header
        value: Awesome
```

- Checks whether the **path** responds on the **port**.
- **HTTP status rule:** `200 ≤ code < 400` → **success**; anything else (e.g. **500**) → **failure**.
- Can send **custom headers**. (Header = metadata on the request, e.g. `Content-Type: application/json`, `Accept-Language: en`, or a size like `Size: XL`.)

**This is the most common mechanism** for web apps and APIs.

### 2. `tcpSocket` — is the port open?

```yaml
readinessProbe:
  tcpSocket:
    port: 3306
```

- Just checks whether **a port is open** in the container.
- **Does not know** if the app behind the port is functional — only that something is listening.
- **Best when all you know is the port.** If an app owner tells you "my app listens on 3306", you can write the whole probe with zero knowledge of the app's HTTP endpoints.
- Works for **databases and non-HTTP services** (MySQL 3306 is the classic example).

### 3. `exec` — run a command inside the container

```yaml
livenessProbe:
  exec:
    command:
      - cat
      - /tmp/healthy
```

- Runs a command **inside the container** and checks the **exit code**: `0` → success, non-zero → failure.
- **Nuance:** the command executes **in the target container itself**. It does not run somewhere else and check the container from outside.
- Great for file-existence checks, or custom CLI health scripts the app already ships.

### 4. `grpc` (modern addition)

Kubernetes ≥ 1.24 also supports `grpc` probes for gRPC services (native health-checking protocol). Not covered in the lecture, but worth knowing exists.

### Choosing a mechanism

| Situation | Mechanism |
|---|---|
| HTTP/REST app with a health endpoint | **`httpGet`** |
| You only know the port (DB, TCP service) | **`tcpSocket`** |
| Need a file check or a custom script | **`exec`** |
| gRPC service | `grpc` |

---

## 8) The Timers (Every Field, With Defaults)

Five knobs decide when a probe fires and when it counts as failed.

| Timer | Meaning | Default |
|---|---|---|
| **`initialDelaySeconds`** | Wait this long **after the container is Running** before the **first** probe. Lets the app "settle". | **0** |
| **`periodSeconds`** | Interval **between** probes. Probing repeats for the container's whole life. | **10** |
| **`timeoutSeconds`** | **Max time** to wait for a probe response. Exceeding it = a failed attempt. | **1** |
| **`failureThreshold`** | How many **consecutive failures** before the probe is declared failed (→ action taken). | **3** |
| **`successThreshold`** | How many **consecutive successes** before it's considered healthy again (mainly readiness). | **1** |

### How they compose

```
container Running
     │
     ├── wait initialDelaySeconds
     │
     ▼
  probe #1 ──► fail? ──► failures = 1  (below threshold → do nothing)
     │
     ├── wait periodSeconds
     ▼
  probe #2 ──► fail? ──► failures = 2  (still below threshold)
     │
     ├── wait periodSeconds
     ▼
  probe #3 ──► fail? ──► failures = 3  == failureThreshold ──► ACTION
                                                               (readiness: NotReady
                                                                liveness: restart
                                                                startup: restart)
```

- **One failure does nothing** if `failureThreshold` is 3 — deliberate dampening against false positives.
- Failure #3 triggers the action.

### Tuning is application-specific

- **Critical, latency-sensitive app** → shorten `periodSeconds` from 5 s to 2 s so failure is detected faster.
- **Flaky app that self-heals** → raise `failureThreshold` so a small deadlock doesn't cause a restart.
- **The decision belongs to you + the application developer + the chief engineer** — not to a default.

> You only declare the timers you care about; **the rest come from defaults**. Verified in the demo: `kubectl get pod -o yaml` shows **all five** fields even when the manifest declared only three.

---

## 9) Demo 1 — Readiness Probe

### The manifest (`rp.yaml`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: readiness-probe-demo
spec:
  containers:
    - name: readiness
      image: busybox
      command:
        - "sh"
        - "-c"
        - "touch /tmp/ready && sleep 3600"
      readinessProbe:
        exec:
          command:
            - cat
            - /tmp/ready
        initialDelaySeconds: 5
        periodSeconds: 5
        failureThreshold: 1
```

**The simulation:** create `/tmp/ready`, then sleep for an hour. The probe is simply *"can I `cat` `/tmp/ready`?"* — so the file's existence **is** the health signal.

- `initialDelaySeconds: 5` → 5 s to settle before the first check.
- `periodSeconds: 5` → check every 5 s.
- `failureThreshold: 1` → **a single failure fails the probe** (very aggressive — for demonstration).

### Apply and inspect

```bash
kubectl apply -f rp.yaml
kubectl get pods
# NAME                    READY   STATUS    RESTARTS   AGE
# readiness-probe-demo    1/1     Running   0          8s
```

Note the first `get pods` right after apply may show `Running` at the **pod** level before the container reports ready — a second later it's `1/1`.

### Confirm the probe in `describe`

```bash
kubectl describe pod readiness-probe-demo
```

```
Readiness:  exec [cat /tmp/ready] delay=5s timeout=1s period=5s #success=1 #failure=1
```

Note the mechanism rendered as **`exec`**, because we're running a command.

### Confirm defaults in the YAML

```bash
kubectl get pod readiness-probe-demo -o yaml
```

The probe block shows **all five** timers — including `timeoutSeconds: 1` and `successThreshold: 1`, which we never wrote. **Unspecified timers inherit defaults.**

### Simulate failure — delete the file

```bash
kubectl exec -it readiness-probe-demo -- /bin/sh
# inside:
ls /tmp            # ready exists
rm /tmp/ready
exit
```

```bash
kubectl get pods
# readiness-probe-demo   0/1   Running   0   2m
```

**`0/1`** — the container is still `Running`, but **not ready**. And it happened within one probe period:

```bash
kubectl describe pod readiness-probe-demo
```

```
Warning  Unhealthy  Readiness probe failed: cat: can't open '/tmp/ready': No such file or directory
```

### The critical observation — **no restart**

```
RESTARTS: 0
```

The container was **not restarted**, because this is a **readiness** probe. It was simply pulled out of rotation.

That's precisely the scenario readiness is designed for: a file momentarily inaccessible, a process briefly hung, some temporary resource pressure. You **do not** want a restart. You want the pod to stop receiving traffic and recover.

### Recover — recreate the file

```bash
kubectl exec -it readiness-probe-demo -- /bin/sh
# inside:
touch /tmp/ready
exit

kubectl get pods
# readiness-probe-demo   1/1   Running   0   4m
```

Back to **ready**, no restart, within one period.

### A small observation about events

`kubectl describe` / `kubectl events` did **not** record a "pod became ready again" event — the failure was logged as a `Warning`, but the recovery was silent.

**Trust `kubectl get pods`.** `Running` + `1/1` means all containers are healthy and ready; the absence of an event is not evidence of a problem.

---

## 10) Demo 2 — Liveness Probe

### The purpose-built image

Kubernetes maintains a **demo image** specifically for practicing liveness. Its behaviour:

| Time since container start | `/healthz` response |
|---|---|
| **First 10 seconds** | **HTTP 200** → probe succeeds |
| **After 10 seconds** | **HTTP 500** → probe fails → container restarted |

So the container is **healthy for 10 s, then permanently unhealthy** — perfect for watching restarts happen.

> **HTTP status rule again:** `200–399` = success, everything else (including `500`) = failure.

### The manifest (`lp.yaml`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: liveness-probe-demo
spec:
  containers:
    - name: liveness
      image: registry.k8s.io/liveness        # the demo image
      args:
        - /server
      livenessProbe:
        httpGet:
          path: /healthz
          port: 8080
          httpHeaders:
            - name: Custom-Header
              value: Awesome
        initialDelaySeconds: 3
```

- `httpGet` on `/healthz`, port **8080**.
- A **custom header** is attached (`Custom-Header: Awesome`) — just to show the capability; the demo server ignores it.
- `initialDelaySeconds: 3` → first check at 3 s, while the app is still healthy.
- Everything else defaults: period **10 s**, timeout **1 s**, failureThreshold **3**.

### What you should expect

```
t=0     container starts
t=3     probe #1 → 200 → OK
t=10    app flips to 500
t=13    probe #2 → 500 (failure 1)
t=23    probe #3 → 500 (failure 2)
t=33    probe #4 → 500 (failure 3) → RESTART
```

Roughly **every 15 seconds** you'll see another restart in practice, and the **`RESTARTS` counter climbs**: 1, 2, 3 …

### Watch it

```bash
kubectl apply -f lp.yaml
kubectl get pods
# liveness-probe-demo   1/1   Running   0   5s

# wait, then:
kubectl get pods
# liveness-probe-demo   1/1   Running   1   18s      ← restarted 5s ago

kubectl get pods
# liveness-probe-demo   1/1   Running   3   1m
```

Each restart resets the clock: fresh 10 s of health, then failure again. **Forever.**

### When it becomes `CrashLoopBackOff`

```bash
kubectl get pods
# liveness-probe-demo   0/1   CrashLoopBackOff   5   3m
```

> Whenever there are **multiple restarts** and the application **still** isn't working, you see **`CrashLoopBackOff`** (Day 22: exponential backoff, 10 → 20 → 40 … capped at 5 min).

So a liveness probe with a wrong config or a genuinely broken app **converges to `CrashLoopBackOff`** — the same status family as any other crash.

### Reading it correctly

| Suspicion | Reality |
|---|---|
| "The pod is `Running`, so the app is fine" | It's `Running` **1/1** — but restarts prove the app keeps failing |
| "`CrashLoopBackOff` means my image is broken" | Not necessarily — here the **probe** is killing a healthy-at-boot app |

> `RESTARTS` is the number to watch. A pod that is `Running` with a climbing restart count is a pod being repeatedly killed by something — often liveness.

---

## 11) Demo 3 — Startup Probe + `tcpSocket`

The last missing mechanism is **TCP socket**, and it pairs naturally with a **slow-starting** container.

### The manifest (`sp.yaml`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: startup-probe-demo
spec:
  containers:
    - name: startup
      image: ubuntu
      command:
        - "sh"
        - "-c"
        - "apt update && apt install -y netcat-openbsd && nc -l 94"
      startupProbe:
        tcpSocket:
          port: 94
        periodSeconds: 5
        failureThreshold: 15
```

### Why this is deliberately slow

The command does **three expensive things** before the port ever opens:

1. `apt update` — refresh the package index (**needs network + time**)
2. `apt install -y netcat-openbsd` — install netcat (`nc`)
3. `nc -l 94` — **netcat listens on port 94**

Only after step 3 is port 94 open — and port 94 is exactly what the probe checks.

> The instructor notes he couldn't find an image with netcat pre-installed, hence the install dance. That's convenient: it makes the container genuinely slow, which is the point.

### The budget calculation (the key insight)

```
failureThreshold (15) × periodSeconds (5s) = 75 seconds
```

So the startup probe gives this container **75 seconds** to finish installing and start listening.

| Outcome | Result |
|---|---|
| Port 94 opens **within 75 s** | Startup probe succeeds → readiness/liveness begin → probe **never runs again** |
| Port 94 does **not** open in 75 s | Startup probe fails → **container restarted** |

> That's the entire purpose: **"I have a slow container that may take 75 seconds to start. If it doesn't start in time, restart it."**

### Apply and observe

```bash
kubectl apply -f sp.yaml
kubectl get pods
# NAME                 READY   STATUS    RESTARTS   AGE
# startup-probe-demo   0/1     Running   0          20s
```

**The pod can show `Running` while `0/1`.** Why?

- `Running` is the **pod phase** — the container process exists and is executing (it's running `apt`!).
- `0/1` is **readiness** — no app container has reported ready yet, because there's no readiness probe and the container is still in its startup window.

```
Pod phase (Running)  ≠  container readiness (0/1)
```

And the startup probe is the reason nothing is "ready" yet: **readiness and liveness are gated until it succeeds**.

### The lifecycle point

> **Startup probes do not run continuously.** Readiness and liveness live with the container for life; the startup probe **retires** the moment it succeeds.

```
startup probe: runs once, at boot, then gone
readiness:     from Running until termination
liveness:      from Running until termination
```

**Same shape as init containers**: appear at the beginning, do their job, disappear.

---

## 12) Readiness vs Liveness vs Startup — One Table

| | **Readiness** | **Liveness** | **Startup** |
|---|---|---|---|
| **Question asked** | *Can this pod serve traffic?* | *Is this container still alive?* | *Has it finally finished booting?* |
| **On failure** | Pod marked **`NotReady`**, removed from Service endpoints | **Container restarted** | **Container restarted** |
| **Restarts?** | **No** | **Yes** | **Yes** |
| **When it runs** | From `Running`, for life | From `Running`, for life | **Only at start-up**, then stops |
| **Multi-container effect** | **Whole pod** loses traffic | **Only the failing container** restarts | Only the failing container restarts |
| **Fixes** | Temporary problems | Irrecoverable hangs | Too-slow boot |
| **Typical use** | DB conn init, app init, brief overload | Deadlock, hung state, memory leak | Slow initializing apps |
| **Default mechanism in demos** | `exec` | `httpGet` | `tcpSocket` |
| **Gates the others?** | No | No — but **gated by startup** | **Yes** — nothing else runs until it passes |

### The one-line memory hook

- **Readiness** → *"don't send me traffic."*
- **Liveness** → *"kill me and start over."*
- **Startup** → *"give me time, then judge me by the other two."*

---

## 13) Best Practices

1. **Don't probe the port you serve business traffic on with a shallow check.** A `tcpSocket` probe says "the port is open" — it doesn't say the app works. Prefer a real health endpoint (`/healthz`) when the app can provide one.
2. **`failureThreshold: 1` is for demos, not production.** One blip → outage. Use 3+ and let the threshold dampen false positives.
3. **Only use liveness for irrecoverable states.** Anything self-healing belongs in readiness.
4. **Set `initialDelaySeconds` honestly** — a probe that fires before the app is listening will kill it instantly, and `CrashLoopBackOff` follows.
5. **Use startup probes instead of huge `initialDelaySeconds` on liveness.** The startup probe gives slow apps time **without** weakening steady-state liveness.
6. **Tune `periodSeconds` to criticality.** 2 s for latency-critical services; longer for batch-like workloads.
7. **Tune `timeoutSeconds`** if the app legitimately responds slowly — default 1 s is tight.
8. **Set `successThreshold` > 1** for flappy readiness if you want stability before rejoining the load balancer.
9. **Probes are per container.** In a multi-container pod, probe the containers whose health actually matters — you don't have to probe them all.
10. **Decide with the app owner.** The instructor's repeated point: timers are **application-specific**, and the final call is between you, the developer, and the chief engineer.

---

## 14) Key Takeaways

1. **Probes solve three things:** only healthy pods take traffic (**readiness**), deadlocked pods get restarted (**liveness**), slow apps get time to boot (**startup**).
2. **Pod status = worst container's status.** `1/2` + `ErrImagePull` means one container is broken and the pod says so.
3. **Probing only starts when the container is `Running`** — you cannot probe a container stuck in `ErrImagePull`.
4. **The kubelet performs the probes** on its node and **reports health to the API server**. Probes are defined per container in the pod spec.
5. **Readiness failure → pod `NotReady`, removed from load balancing, NO restart.** Runs for the container's whole life.
6. **One container failing readiness takes the WHOLE pod out of rotation** — even healthy containers get zero traffic.
7. **Liveness failure → container restarted.** Runs for the container's whole life.
8. **Liveness failure restarts ONLY the failing container** — other containers are untouched. This is the key readiness/liveness contrast in multi-container pods.
9. **Startup probes are for slow boot and stop after one success.** Readiness and liveness **do not begin until the startup probe passes.**
10. **Startup budget = `failureThreshold × periodSeconds`.** 15 × 5 s = **75 s** in the demo; exceed it and the container restarts.
11. **Mechanisms are probe-agnostic:** `httpGet` (path+port; **200–399 = success**), `tcpSocket` (port open), `exec` (command exit code 0), plus `grpc`.
12. **`exec` runs inside the container itself** — not from outside.
13. **Default timers:** `initialDelaySeconds: 0`, `periodSeconds: 10`, `timeoutSeconds: 1`, `failureThreshold: 3`, `successThreshold: 1`. Unspecified timers are **auto-filled** and visible in `kubectl get pod -o yaml`.
14. **A liveness probe with a bad config converges to `CrashLoopBackOff`** — the `RESTARTS` counter is the tell.
15. **`Running` + `0/1` is normal during startup** — pod phase and container readiness are different things.

---

## 15) Essential Snippets

```yaml
# --- Readiness: exec, file-existence check ---
    readinessProbe:
      exec:
        command: ["cat", "/tmp/ready"]
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 1

# --- Liveness: httpGet with custom header ---
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
        httpHeaders:
          - name: Custom-Header
            value: Awesome
      initialDelaySeconds: 3
      periodSeconds: 10
      timeoutSeconds: 1
      failureThreshold: 3
      successThreshold: 1

# --- Startup: tcpSocket on a slow-starting container ---
    startupProbe:
      tcpSocket:
        port: 94
      periodSeconds: 5
      failureThreshold: 15      # 15 × 5s = 75s of boot budget

# --- tcpSocket on a database port ---
    readinessProbe:
      tcpSocket:
        port: 3306
      initialDelaySeconds: 10
```

```bash
# Apply and watch
kubectl apply -f rp.yaml
kubectl get pods
kubectl get pods -w

# Inspect the probe as Kubernetes sees it
kubectl describe pod <pod>              # Readiness:/Liveness: line

# Inspect ALL timers (including defaults)
kubectl get pod <pod> -o yaml

# Simulate / verify failures
kubectl exec -it <pod> -- /bin/sh       # rm /tmp/ready, then touch it back
kubectl describe pod <pod>              # Warning Unhealthy: Readiness probe failed...

# Failure events
kubectl events
```

---

## 16) Quick Self-Check

1. Name the three probe types and the one sentence each is responsible for.
2. Why can't a container stuck in `ErrImagePull` be probed?
3. Which component performs probes, and where does it run?
4. A pod has 2 containers; one fails its readiness probe. Do the healthy container's requests get served? Why?
5. Same pod; one container fails its **liveness** probe. What happens to the other container?
6. Which probe never restarts a container? Which two always do?
7. Do readiness and liveness run before the startup probe succeeds?
8. How long does a startup probe keep running once it succeeds once?
9. A startup probe has `periodSeconds: 10` and `failureThreshold: 6`. How long is the boot budget?
10. Which HTTP status codes count as probe success?
11. What's the exit-code rule for an `exec` probe? Where does the command run?
12. List the five timers and their defaults.
13. With defaults and a permanently failing liveness probe, how many consecutive failures before the restart?
14. A pod shows `Running` but `0/1` with a startup probe configured. Explain both fields.
15. Your app takes 90 s to boot and has a liveness probe with a 10 s initial delay. What happens, and what should you change?
16. For a MySQL container where you only know the port, which mechanism do you use?

---

## What's Next (Day 24)

- **Docker volumes** — image layers, read-only vs writable layers, storage drivers vs volume drivers, and named / bind / tmpfs volumes.
- Then **Kubernetes core & plugins (CRI/CNI/CSI)** on Day 25, and **Kubernetes volumes** on Day 26.

---

*End of Day 23 notes.*
