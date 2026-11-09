# Pod Security — Security Contexts & Linux Capabilities (Day 41)

> Source: Day 41 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Why containers running as root is a problem, and the two levers that fix it — **`securityContext`** (pod and container level) and **Linux capabilities** (container level only).
> Prerequisite: Day 19 (requests/limits), Day 22 (container lifecycle), Day 38 (**admission control** — how you *enforce* these settings).
> Next: Day 42 — *"I haven't finalized the topic yet… it's going to be a surprise."*

---

## 1) Why Pod Security at All?

> **Kubernetes lets you run containers easily. It does not secure them by default.**

Every pod you've created in this course — nginx, busybox, ubuntu — had **no** security parameters. So you got the **default**: **processes running as `root` (UID 0)**.

### See it for yourself

```bash
kubectl run my-pod --rm -it --image=busybox -- sh
```

Inside the container:

```sh
id
# uid=0(root) gid=0(root) groups=0(root),10(wheel)

whoami
# root
```

| Output | Meaning |
|---|---|
| **`uid=0`** | **User ID 0** — the **first user in Linux**, which is **root** |
| **`gid=0`** | The **root group** |
| **`groups=0(root),10(wheel)`** | `wheel` is the **administrative group** — the one that grants `sudo`/`su` |

> And if you create or modify a file in that container, it will be **owned by root**.

---

## 2) The Principle of Least Privilege

> **Grant only the permissions needed to perform the task. No extra permissions.**

This is the first thing to think about in any production security review — for **cloud accounts, system users, and containers alike**.

A container whose only job is *"serve HTTP on port 80"* does **not** need to change system time, modify network interfaces, or own the filesystem.

> Root inside a container is **far more privilege than the job requires** — the textbook violation.

---

## 3) What Root Buys an Attacker (and an Accident)

### 3.1 Privilege escalation

> If the container is compromised, an attacker can **escalate privileges and try to break out of the container**.

Since the process is already root:

- **Every root-level operation** inside the container is available to the attacker.
- If **special permissions** are granted (privileged mode, dangerous capabilities), the container can reach the **underlying host's kernel**.

> Root-in-container is not automatically root-on-host — but it's one step and one misconfiguration away. That's the point.

### 3.2 Host access in weakly isolated environments

> In environments **without user namespaces or pod security standards**, a root container can gain **elevated access to the host system**.

**User namespaces** are the kernel feature that maps container-root to an unprivileged host user. Without them, `uid=0` in the container **is** `uid=0` on the host for many purposes.

> The default is the *weak* configuration. Isolation has to be **turned on**.

### 3.3 Accidental misuse — no attacker required

This is the argument people forget:

> *"Keep aside malicious actors… what if an application running as root **unintentionally** modifies critical files or performs actions that would otherwise be restricted?"*

A bug, a bad config path, a wildcard in a delete command — with root privileges there is **nothing stopping it**. **Your own application becomes the threat.**

### 3.4 Non-compliance

> **Security is subjective; compliance is not.**

| | **Security** | **Compliance** |
|---|---|---|
| Defined by | You, your team, your org | **Third-party standards** |
| Varies per org? | ✅ yes | ❌ no — it's a published rulebook |
| Enforceable? | By convention | **By audit** |

If a compliance standard your application must meet says *"processes run as non-root"*, then **root = non-compliance** — regardless of whether it "works".

> Especially relevant in regulated industries. And in general, least privilege says a non-root user is the correct default.

---

## 4) Not All Images Run as Root — But Don't Assume

Some images are **built** to run as non-root. Example Dockerfiles:

```dockerfile
# Example 1 — create a user, switch to it
FROM ubuntu
RUN useradd -u 1000 -m appuser
USER appuser
CMD ["./app"]
```

```dockerfile
# Example 2 — just the numeric UID
FROM ubuntu
USER 1000
CMD ["./app"]
```

### The Linux lesson worth internalising

> **Usernames exist for humans. The kernel only cares about numeric UID and GID.**

That's why `USER 1000` works without any username being created — and why you'll see `id` print `uid=1000` with **no name** at all (see Demo 1).

### "But distroless/Bitnami images don't run as root…"

> **Don't rely on that.** You do not know an image's user **until you check its Dockerfile or inspect the running container**.

The instructor's position is firm:

> **DevOps/infrastructure engineers should not depend on image authors.** **Explicitly define security context fields**, and **enforce** them with policy.

### Where enforcement comes from

> **Admission control** (Day 38) — reject any pod that doesn't meet your security requirements.

**Setting** a security context protects one pod. **Enforcing** it protects the cluster.

---

## 5) The Two Levers

```
Pod security
├── securityContext        ← pod level AND container level
└── Linux capabilities     ← container level ONLY
```

| | **`securityContext`** | **Linux capabilities** |
|---|---|---|
| Levels | **Pod** *and* **container** | **Container only** |
| Declared under | `spec.securityContext` / `containers[].securityContext` | `containers[].securityContext.capabilities` |
| Controls | User, group, privilege escalation, root FS, volumes | Individual **root-level** permissions |

> Only these two are covered — *"there are a few more concepts… not relevant at least for now."* (See Section 12 for what's beyond.)

---

## 6) `securityContext` — the Three Groupings

### 6.1 Pod level only

| Field | Meaning |
|---|---|
| **`fsGroup`** | The **GID that owns mounted volumes** — so the container can write to them |
| `fsGroupChangePolicy` | When to re-apply that ownership (`OnRootMismatch` / `Always`) |

> `fsGroup` only makes sense **if you mount a volume** — which is exactly why Demo 2 introduces one.

### 6.2 Pod **and** container level

| Field | Meaning |
|---|---|
| **`runAsUser`** | UID to run the process as |
| **`runAsGroup`** | Primary GID for the process |
| **`runAsNonRoot`** | **Refuse to start** if the image would run as **root** |

**The precedence rule:**

> Set at **pod** level → applies to **all containers** in the pod.
> Set at **container** level → applies to **that container**.
> **Set at both → the container wins.**

### 6.3 Container level only

| Field | Meaning |
|---|---|
| **`allowPrivilegeEscalation`** | Can the process **gain** privileges (via setuid binaries)? |
| **`privileged`** | **Full host access**, including kernel-level operations |
| **`readOnlyRootFilesystem`** | Mounts the container's **root filesystem read-only** |
| **`capabilities`** | Add/drop individual Linux capabilities |

---

## 7) The Fields in Plain English

### `runAsNonRoot: true` — a hard gate

> *"No matter what, your containers will not start with the root user."*

Try it with `nginx` (whose image runs as root by default):

```yaml
securityContext:
  runAsNonRoot: true
```

```
Error: container has runAsNonRoot and image will run as root
```

> The pod enters `CreateContainerConfigError` and **never starts**. That's the feature working: it converts *"we meant to fix that"* into *"the deployment is broken"* — which someone will notice.

### `allowPrivilegeEscalation: false` — the setuid defence

> **The setuid bit:** a binary **owned by root** with **setuid** set runs with **root privileges even when a non-root user executes it**.

So a container running as **UID 1000** can still reach root **if it can run a setuid binary**.

```yaml
allowPrivilegeEscalation: false
```

> This sets the kernel's **`no_new_privs`** flag — **no setuid, no capability gain, no escalation**. The non-root container **stays** non-root.

### `privileged: true` — never in production

> **Full access to the host, including kernel-level operations.**

Practical rule: **`privileged: false`** everywhere, always. It exists for special cases (CNI plugins, some storage drivers) and is a **red flag** in application manifests.

### `readOnlyRootFilesystem: true` — if the app doesn't write, why allow it?

> *"If my application is not performing any modifications to system-level configuration files or system files, then why do I have to give it permission to modify something?"*

```yaml
readOnlyRootFilesystem: true
```

- **Anything under `/`** (the container's root) **cannot be created or modified**.
- Writes fail with **`Read-only file system`**.

### The obvious objection: "what if my app needs to write?"

> Mount a **volume** — `emptyDir`, `hostPath`, or (recommended) a **PVC** — and give the app **write access to that mount**, not the whole filesystem.

And that's where **`fsGroup`** earns its place:

> **`fsGroup` specifies the GID that owns the mounted volume.** With it, the mounted directory is **group-owned** by that GID, and the container's user (a member of that group) can **create, modify, and delete files inside it**.

**The combination:**

```
readOnlyRootFilesystem: true   ← system files protected
        +
fsGroup: 2000                  ← one mounted volume is writable by GID 2000
        +
runAsUser: 1000                ← the process runs unprivileged
```

> **Narrow write access**: the app can write **exactly where it needs to**, and nowhere else. That's least privilege applied to filesystems.

---

## 8) Demo 1 — Pod & Container Security Context

### The manifest

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-pod
spec:
  securityContext:                  # POD level
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000
    runAsNonRoot: true
  containers:
    - name: app
      image: busybox
      command: ["sh", "-c", "sleep 3600"]
      securityContext:              # CONTAINER level
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
```

> Note `fsGroup: 2000` does **nothing yet** — no volume is mounted. Demo 2 fixes that deliberately, so the two settings can be seen **working together**.

```bash
kubectl apply -f 01-secure-pod.yaml
kubectl exec -it secure-pod -- sh
```

### Test 1 — write to the root filesystem

```sh
mkdir test_dir
# mkdir: can't create directory 'test_dir': Read-only file system
```

> **`readOnlyRootFilesystem: true` at work.**

### Test 2 — try to become root

```sh
su -
# sh: su: not found
sudo su
# sh: sudo: not found
```

> BusyBox doesn't ship `sudo`/`su` — *"but even if it had them, these commands wouldn't run because we supplied `allowPrivilegeEscalation: false`."*

### Test 3 — who am I really?

```sh
id
# uid=1000 gid=3000 groups=...
```

> **`uid=1000`** — as configured. `gid=3000` — as configured.
>
> The username reads **`unknown`** — **that is not an error.** There's no `/etc/passwd` entry for UID 1000 in this image. *"Linux security is based on UIDs and GIDs, not usernames. Usernames are optional, only for human readability."*

### Test 4 — what is the process running as?

```sh
ps aux
# ... sleep 3600 ... (UID 1000)
```

> **The actual process is UID 1000.** Without the security context, that same command would run as **root** — the problem from Section 1, now fixed.

---

## 9) Demo 2 — Writable Volumes via `fsGroup`

### The manifest

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-writable
spec:
  securityContext:
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000               # ← now it matters
    runAsNonRoot: true
  containers:
    - name: app
      image: busybox
      command: ["sh", "-c", "sleep 3600"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
      volumeMounts:
        - name: writable-volume
          mountPath: /writable
  volumes:
    - name: writable-volume
      emptyDir: {}
```

> **Root FS stays read-only. The mounted volume is the escape hatch.**

### Inspect the ownership

```bash
kubectl exec -it secure-writable -- sh
ls -lr /
```

```
drwxrwxrwx  ... root root   tmp
drwxrwsrwx  ... root 2000   writable      ← GID 2000!
```

| Directory | Owner | Meaning |
|---|---|---|
| `/writable` | **`root:2000`** | **`fsGroup: 2000`** granted **group ownership** of the mounted volume |
| Others | `root:root` | Untouched |

> And **the container's user (UID 1000) is a member of group 2000** — which is why it can now write there.

### The two-sided test

```sh
mkdir /testdir
# mkdir: can't create directory '/testdir': Read-only file system   ❌ root protected

cd /writable
mkdir testdir
# ✅ works
touch myfile
# ✅ works
```

```sh
ls -lr /writable
# drwxrwsr-x  root 2000  testdir
# -rw-r--r--  1000 2000  myfile      ← owned by UID 1000, GID 2000
```

> **Exactly the intended behaviour:** the app **cannot** write to system paths, and **can** write to its designated volume.
>
> *"The GID 2000 has writes on the writable directory."*

---

## 10) Linux Capabilities

### The concept

> **Root privileges are not one thing — they're a bundle of distinct low-level permissions called capabilities.**

| Instead of… | You can grant… |
|---|---|
| **Full root** | *"This container may modify system time, but **not** network settings"* |

> **Capabilities are small bifurcations of root privilege.** They let you **grant** specific root-level abilities and **deny** the rest.

### The three named in the lecture

| Capability | Allows |
|---|---|
| **`CHOWN`** | **Change file/directory ownership** (`chown`) |
| **`SYS_TIME`** | **Set the system clock** — time services, NTP, `date -s` |
| **`NET_ADMIN`** | **Modify network interfaces, routing tables, firewall rules** |

> Not a comprehensive list — the important ones. Others you'll meet: `NET_RAW` (raw sockets/ping), `SYS_ADMIN` (mount, namespaces — extremely powerful), `SYS_PTRACE` (inspect other processes), `DAC_OVERRIDE` (bypass file permissions).

### **Capabilities are container-level only**

> The lecture is explicit: there is **no separate capabilities block in the container spec**. It lives **under `securityContext`**:

```yaml
      securityContext:
        capabilities:
          drop: ["ALL"]
          add: ["NET_ADMIN", "SYS_TIME"]
```

> **`drop` and `add` — you can remove capabilities as well as grant them.** `drop: ["ALL"]` starts from zero privilege, which is the correct baseline.

---

## 11) Demo 3 — Dropping and Testing Capabilities

### The manifest (`cap-pod`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: cap-pod
spec:
  containers:
    - name: app
      image: busybox
      command: ["sh", "-c", "sleep 3600"]
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
          add: ["NET_ADMIN", "SYS_TIME"]     # NOT CHOWN
```

> Notice: **no `runAsUser`** — so this pod still runs as **root**. Capabilities are an **orthogonal** control: you can restrict a root container's powers without changing its UID.

```bash
kubectl apply -f 03-capability-pod.yaml
kubectl exec -it cap-pod -- sh
id
# uid=0(root)  gid=0(root)    ← still root
```

### Test 1 — `NET_ADMIN` works

```sh
ip link show
# 1: lo: <LOOPBACK,UP,LOWER_UP> ...

ip link set lo down
ip link show
# 1: lo: <LOOPBACK> ...        ← UP is gone; the interface is down ✅
```

> **Granted `NET_ADMIN` → allowed.** Then restore it (`ip link set lo up`) so the container stays usable.

### Test 2 — `SYS_TIME` works

```sh
date
# Sat Jun 28 ...

date -s "2025-06-01 10:00:00"
date
# Sun Jun 1 10:00:00 ...      ← the clock CHANGED ✅
```

> **Granted `SYS_TIME` → allowed.**

### Test 3 — `CHOWN` does *not* work (it was never granted)

```sh
touch myfile
ls -lr myfile
# -rw-r--r--  root root  myfile      ← root owns it

chown 1000:1000 myfile
# chown: operation not permitted     ❌
```

> **This is the whole lesson.** The process is **root** — normally `chown` would just work — but we **dropped `ALL`** and added back only two capabilities. **`CHOWN` is gone, so ownership changes are impossible.**
>
> *"This is not permitted because in our YAML we said drop all other capabilities and only allow these."*

### Test 4 — the control: drop **everything**

Modify the manifest (rename to `cap-pod-2`), keeping only:

```yaml
        capabilities:
          drop: ["ALL"]
```

```bash
kubectl apply -f 03-capability-pod.yaml
kubectl exec -it cap-pod-2 -- sh

date -s "2025-06-01 10:00:00"
# date: can't set date: Operation not permitted   ❌
```

> **Even the previously-working `SYS_TIME` command now fails** — because nothing was added back. Same for `ip link set lo down`.
>
> **No `add` list = a container with root's UID but none of root's capabilities.** That's a genuinely strong default.

---

## 12) The Recommended Workflow (and What's Beyond)

### The instructor's method for capabilities

> **Start by dropping `ALL`. Then add back only what the application actually needs.**

| Step | Action |
|---|---|
| 1 | Set `drop: ["ALL"]` — start from **zero** privilege |
| 2 | Run the application and **observe the failure** |
| 3 | Read the error, work with the app team, **add the one capability** required |
| 4 | Repeat — never add speculatively |

> *"Do **not** start with add all. **Never.**"*

**Always include a `capabilities` block** — a container with root's UID and root's full capability set is exactly the risk from Section 3.

### What's outside this lecture (but part of pod security)

The lecture names only "the two most important" levers. In practice you'll also meet:

| Mechanism | Purpose |
|---|---|
| **`seccompProfile`** | Restrict which **syscalls** a container may make (`RuntimeDefault` is the safe baseline) |
| **AppArmor / SELinux** | Mandatory access control profiles |
| **Pod Security Standards / Admission** | **`baseline`**, **`restricted`** profiles enforced by namespace labels — **the enforcement layer** for everything in this lecture |
| **User namespaces** | Map container-root to an unprivileged host user |

> These are **enforcement** mechanisms (Day 38's admission control), whereas today's fields are **declaration**. You need both: declare what each pod may do, and **reject** pods that don't.

### The recommended values (worth memorising)

```yaml
securityContext:            # pod level
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 3000
  fsGroup: 2000
containers:
  - securityContext:        # container level
      allowPrivilegeEscalation: false
      privileged: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
```

---

## 13) Key Takeaways

1. **Kubernetes does not secure containers by default** — a plain pod runs as **`uid=0` (root)**, group `root`, often in `wheel`.
2. **Least privilege** is the governing principle: grant only what the task needs.
3. **Root risks:** **privilege escalation** and container breakout, **host access** in weakly isolated environments (no user namespaces), **accidental misuse** by the app itself, and **non-compliance**.
4. **Security is subjective; compliance is not** — third-party standards can *require* non-root.
5. **Some images run as non-root by design** (a `USER` line in the Dockerfile) — but **don't assume**; verify and **enforce**.
6. **Linux only cares about numeric UID/GID**, not usernames — `uid=1000` with no name is normal.
7. **Two levers:** **`securityContext`** (pod *and* container) and **Linux capabilities** (container only).
8. **`securityContext` groupings:** pod-only (`fsGroup`), pod-or-container (`runAsUser`, `runAsGroup`, `runAsNonRoot`), container-only (`allowPrivilegeEscalation`, `privileged`, `readOnlyRootFilesystem`, `capabilities`).
9. **Precedence:** pod-level applies to all containers; **container-level wins** when both are set.
10. **`runAsNonRoot: true` refuses to start** a root-running image — it's a hard gate, not a hint.
11. **`allowPrivilegeEscalation: false`** blocks **setuid** binaries from regaining root inside a non-root container.
12. **`privileged: true` = full host/kernel access** — never in production.
13. **`readOnlyRootFilesystem: true`** blocks all writes under `/` — *"if the app doesn't write, why allow it?"*
14. **Writes belong on a mounted volume**, not the root FS — and **`fsGroup`** makes that volume **group-writable** by the container's user.
15. **The pattern:** read-only root + one writable mount owned by `fsGroup` = **narrow, auditable write access**.
16. **Capabilities are bifurcations of root** — grant `SYS_TIME` without granting `NET_ADMIN`.
17. **`CHOWN`** = ownership changes · **`SYS_TIME`** = system clock · **`NET_ADMIN`** = interfaces/routing/firewall.
18. **Capabilities live under `containers[].securityContext.capabilities`** with **`drop`** and **`add`** — there is no separate block.
19. **`drop: ["ALL"]` is the correct baseline**, then add back one capability at a time based on real errors.
20. **Never start with `add: ["ALL"]`. Never.**
21. **Capabilities are orthogonal to UID** — a container can run as root and still be stripped of nearly all power.
22. **Declaring is not enforcing.** Use **admission control** (Day 38) / **Pod Security Standards** to reject non-compliant pods.

---

## 14) Essential Commands

```bash
# --- Prove the default is root ---
kubectl run my-pod --rm -it --image=busybox -- sh
#   id        → uid=0(root) gid=0(root) groups=0(root),10(wheel)
#   whoami    → root

# --- Apply and inspect security contexts ---
kubectl apply -f 01-secure-pod.yaml
kubectl exec -it secure-pod -- sh
#   id                          → uid=1000 gid=3000
#   mkdir test_dir              → Read-only file system
#   sudo su / su -              → not found (and escalation is blocked anyway)
#   ps aux                      → sleep 3600 as uid 1000

# --- Writable volume with fsGroup ---
kubectl apply -f 02-secure-writable.yaml
kubectl exec -it secure-writable -- sh
#   ls -lr /                    → writable root:2000
#   mkdir /testdir              → ❌ Read-only file system
#   cd /writable && mkdir testdir && touch myfile   → ✅
#   ls -lr /writable            → 1000:2000

# --- Capabilities ---
kubectl apply -f 03-capability-pod.yaml
kubectl exec -it cap-pod -- sh
#   ip link show                → lo is UP
#   ip link set lo down         → ✅ (NET_ADMIN granted)
#   date -s "..."               → ✅ (SYS_TIME granted)
#   chown 1000:1000 myfile      → ❌ operation not permitted (CHOWN dropped)

#   # second variant with drop: ["ALL"] only
kubectl exec -it cap-pod-2 -- sh
#   date -s "..."               → ❌ can't set date: Operation not permitted

# --- Inspect what a pod actually got ---
kubectl get pod <pod> -o yaml | Select-String -Pattern "securityContext" -Context 0,8
kubectl describe pod <pod> | Select-String -Pattern "Security Context" -Context 0,5
```

### The recommended baseline

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-writable
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000
  containers:
    - name: app
      image: busybox
      command: ["sh", "-c", "sleep 3600"]
      securityContext:
        allowPrivilegeEscalation: false
        privileged: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
          # add: only what the app provably needs
      volumeMounts:
        - name: writable-volume
          mountPath: /writable
  volumes:
    - name: writable-volume
      emptyDir: {}
```

---

## 15) Quick Self-Check

1. What user does a default pod's process run as? How do you prove it?
2. What do UID 0, GID 0, and the `wheel` group signify?
3. State the principle of least privilege in one sentence.
4. Name the four risks of running containers as root.
5. Why is "accidental misuse" a stronger argument than "hackers" in some organisations?
6. Distinguish security from compliance in this context.
7. How does a Dockerfile make an image run as non-root? Give two ways.
8. Why does `id` sometimes show `unknown` for the username? Is that an error?
9. Why shouldn't you rely on "distroless images don't run as root"?
10. What enforces pod security at the cluster level, and which earlier lecture covered it?
11. Which securityContext fields are pod-only, which are pod-or-container, and which are container-only?
12. If a field is set at both pod and container level, which wins?
13. What happens when `runAsNonRoot: true` meets an image that runs as root?
14. How exactly does `allowPrivilegeEscalation: false` stop a non-root container from becoming root?
15. What does `privileged: true` grant, and should it ever be in an app manifest?
16. Why set `readOnlyRootFilesystem: true`? What error do writes produce?
17. If the app must write data, how do you allow it **without** opening the root filesystem?
18. What does `fsGroup` do, at what level is it declared, and why did it do nothing in Demo 1?
19. In Demo 2, why could UID 1000 write to `/writable` but not to `/`?
20. What is a Linux capability? Give three examples and what each allows.
21. Where in the manifest do capabilities go? Is there a separate container-level block?
22. In Demo 3, the process was root yet `chown` failed. Explain precisely why.
23. Why does `date -s` fail in `cap-pod-2` but work in `cap-pod`?
24. What's the correct sequence for deciding which capabilities to add?
25. Name three pod-security mechanisms beyond this lecture (declaration *and* enforcement).

---

## What's Next (Day 42)

- **Not finalised in the lecture** — *"I haven't finalised the topic yet… it's going to be a surprise."* The security arc continues (expect Pod Security Standards/admission, seccomp, or RBAC/security review territory).

---

*End of Day 41 notes.*
