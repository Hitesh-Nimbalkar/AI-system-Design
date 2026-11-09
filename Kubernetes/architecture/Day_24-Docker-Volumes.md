# Docker Volumes & Container Storage — Complete Notes (Day 24)

> Source: Day 24 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Docker storage — image layers, read-only vs writable layers, storage drivers vs volume drivers, and Docker volumes (named, bind, tmpfs).
> Why it matters: this is the foundation for Kubernetes volumes (Day 25) and CSI.
> Prerequisite: Day 01 (Docker Engine = CLI + REST API + daemon), Day 03 (the Dockerfile used in this lecture), Day 05 (multi-stage builds).

---

## 1) The Problem: Containers Are Ephemeral

The whole lecture exists because of one sentence:

> **Containers are ephemeral. They come and go. When one dies, everything it wrote is gone.**

That is *by design* — a container should be disposable. But real applications produce data that must outlive the container: databases, uploads, logs, generated reports.

**Docker volumes exist so that data you want persisted actually persists.**

---

## 2) The Setup: One Image, Three Containers

The lecture's diagram:

```
                Docker Host
   ┌─────────────────────────────────────────┐
   │  ┌──────────┐  ┌──────────┐  ┌────────┐ │
   │  │container1│  │container2│  │cont. 3 │ │
   │  │ + 4 MB   │  │ + 10 MB  │  │ + 6 MB │ │
   │  └────┬─────┘  └────┬─────┘  └───┬────┘ │
   │       └─────────────┼────────────┘      │
   │              ┌──────▼──────┐            │
   │              │    IMAGE    │ 50 MB      │
   │              │ (read-only) │ (shared)   │
   │              └─────────────┘            │
   └─────────────────────────────────────────┘
```

- One **Dockerfile** (the same one from **Day 03**) produced **one image**.
- The image is **50 MB** — a rounded number "for simplicity"; a real image from that Dockerfile is larger.
- **Three containers** all run from that **same image**.
- The image is **shared** — it is stored **once**, not three times.

### The storage math

| What | Size |
|---|---|
| Image (shared, read-only) | 50 MB |
| Container 1 writable layer | 4 MB |
| Container 2 writable layer | 10 MB |
| Container 3 writable layer | 6 MB |
| **Total on host** | **70 MB** |

Before the containers write anything, total consumption is **just 50 MB** — because they only *share* the image. This is the difference between "three containers each with a 50 MB copy" (150 MB) and reality (50 MB).

---

## 3) Dockerfile Instructions: Layer-Creating vs Non-Layer-Creating

Every instruction falls into one of two buckets.

### Layer-creating instructions

> **Any instruction that generates data or modifies the file system in any way.**

| Instruction | Why it creates a layer |
|---|---|
| **`FROM`** | Pulls a base image, which itself uses storage |
| **`RUN`** | Installs packages / executes commands → writes to the filesystem |
| **`COPY`** | Copies files from build context into the image |
| **`ADD`** | Copies (and can fetch/extract) data from the host into the image |

### Non-layer-creating instructions

> **Metadata for the image.** They don't perform storage-intensive work; they help the container at **build time** or **run time**.

| Instruction | What it does |
|---|---|
| **`WORKDIR`** | Sets the working directory — no storage consumed |
| **`EXPOSE`** | Documents a port |
| **`CMD`** | Default command to run |
| **`ENV`** | Environment variables |
| **`LABEL`** | Image metadata |
| **`USER`** | Which user to run as |

### The rule of thumb

> **More layer-creating instructions → bigger image.**

- Installing many packages in one `RUN` → larger image.
- `COPY`ing a large directory → larger image.

### The fix: multi-stage builds (Day 05)

Split the Dockerfile into **stages**:

```
Stage 1 (build)    → compiler, SDKs, dev dependencies, source code
Stage 2 (runtime)  → only the binary + runtime deps
```

- Things needed **only to build** the software stay in the build stage.
- Things needed **to run** the app go into the runtime stage.
- The **final image keeps only the runtime stage** → dramatically smaller image.

Two stages is just an example — you can have **as many as you need**.

---

## 4) Why Layers Matter: Read-Only vs Writable

This is the concept the rest of the lecture builds on.

### Image = read-only layers

- An image is made of **read-only layers**.
- Why read-only? Because the image is **shared by all containers**, and **no container may modify it**.
- If one container could change the image, every other container would be corrupted.

### The writable layer (copy-on-write delta)

When you **run** a container:

```
container filesystem = image (read-only layers)  +  writable layer (thin, per-container)
```

- Writes go to the **writable layer** — a private delta on top of the shared image.
- Reading an unmodified file reads straight from the image.
- Modifying a file causes it to be **copied up** into the writable layer, then changed.

> **`delta`** — the word the instructor uses for the writable layer: *the difference between the image and what this container has changed.*

### The consequence

| Event | Result |
|---|---|
| Container writes 10 MB | 10 MB added to that container's writable layer |
| Container **dies** | **That 10 MB is gone forever** |
| Container restarts from the image | Back to a clean image — your data is not there |

**No persistence.** That's the whole motivation for volumes.

---

## 5) Demo — Seeing the Layers

The instructor opens **Day 03's directory** (even though we're on Day 24) because that's where the Dockerfile lives.

```bash
# build the image from Day 03's Dockerfile
docker build -t my-image .

# confirm it exists
docker image ls

# inspect the layers
docker history my-image
```

### What `docker history` shows

| Column | Meaning |
|---|---|
| `IMAGE` | Layer ID |
| `CREATED BY` | The instruction that created it |
| `SIZE` | **Storage consumed by that layer** |

Key observation: **only the layer-creating instructions appear with storage — the non-layer-creating ones show `0B`.**

> `docker history` is the proof: `RUN`, `COPY`, `ADD`, `FROM` consume space; `WORKDIR`, `EXPOSE`, `CMD` do not.

This also gives you a practical image-size debugging technique: **run `docker history`, find the fattest layer, fix that instruction.**

---

## 6) Storage Drivers vs Volume Drivers

Docker handles storage with **two different kinds of drivers**, and confusing them is the classic mistake.

| | **Storage driver** | **Volume driver** |
|---|---|---|
| **Manages** | Container's **internal ephemeral** data | **External persistent** data |
| **Lifecycle** | Tied to the **container** — data dies with it | **Independent** of the container |
| **Role** | Builds the **writable layers** on top of read-only layers | Mounts storage from **outside** the container |
| **Analogy** | The container's own scratch disk | An **external hard drive** |
| **Docker examples** | `overlay2` (default), `zfs`, `aufs` (legacy), `btrfs` | `local` (default), AWS/Azure/GCP drivers |
| **Kubernetes equivalent** | **CRI** → storage driver | **CSI plugins** (Day 25) |

### Storage drivers

- Handle the container's **internal ephemeral data** — the writable layer.
- Think of them as a **filesystem for containers**: they manage internal storage and file organization.
- They are the reason a 50 MB image plus a 4 MB delta works at all — stacking layers into one coherent filesystem view.

**Examples:**

| Driver | Notes |
|---|---|
| **`overlay2`** | **Most widely used**, and the **default on Linux** |
| **`zfs`** | Advanced driver |
| **`aufs`** | **Legacy** — superseded by overlay |
| **`btrfs`** | For **large-scale** environments |

**Verify which one you're using:**

```bash
docker info
```

Look for:

```
Storage Driver: overlay2
```

**How Kubernetes does it:** Kubernetes has the **CRI (Container Runtime Interface)**, which talks to the container runtime, which in turn uses the **storage driver**. Same mechanism, one layer of indirection.

### Volume drivers

- Come into play when you **attach external storage** to a container.
- Handle **external persistent data that exists independently of the container's lifecycle**.
- Even if the container dies, **the data stays**.

**The laptop analogy:** attach an external HDD to your laptop. If the laptop crashes, your data is still safe on the drive. Same idea: the volume is storage that lives outside the container's life.

> Think of volume drivers as **external hard drives for containers**.

**Docker examples:**

- **`local`** — the **default** (used in the demo)
- **AWS / Azure / GCP drivers** — mount cloud storage into containers

**Kubernetes equivalent:** **CSI plugins** (Container Storage Interface) — they let Kubernetes map volumes from different cloud providers and sources. Covered next lecture.

### "If I have volume drivers, do I still need storage drivers?"

**Yes.** Containers still use ephemeral data — scratch files, temp caches, logs you don't want to persist. So **both work in conjunction** in any production-grade Docker deployment.

```
writable layer (scratch)     →  storage driver
mounted volume (persistent)  →  volume driver
```

---

## 7) Installation: Docker Engine vs Docker Desktop

### Docker Engine — Linux only

- Architecturally designed for systems with a **Linux kernel**.
- macOS and Windows **do not have a Linux kernel** → Docker Engine **cannot be installed directly** on them.
- On **any Linux distribution**, Docker Engine runs **natively** — Linux is the base.

**Why the Linux kernel dependency?** Because Docker relies on kernel features:

- **Control groups** (cgroups) — resource limits (Day 19 revisited)
- **Network namespaces** — isolation (Day 21 revisited)
- and more.

**Day 01 recap — Docker Engine consists of:**

1. **Docker CLI**
2. **REST API**
3. **Docker daemon**

That's why it's "of paramount importance" — everything else is built on it.

### Docker Desktop — what most of us use

Docker Desktop **bundles**:

| Component | Purpose |
|---|---|
| **Docker Engine** | Actually runs containers |
| **Docker Compose** | Multi-container orchestration |
| **GUI dashboard** | Containers / images / volumes view |

**How does it work on macOS/Windows?**

> Docker Desktop creates a **lightweight Linux virtual machine**, and installs the **Docker Engine inside that VM**.

- On **macOS**: the VM is created via the **Apple Virtualization Framework**.
- On **Windows**: via **WSL 2** (Windows Subsystem for Linux).

This single fact explains one of the demo's "errors" in the next section.

---

## 8) Demo — Creating and Using a Volume

### Step 1 — Create the volume

```bash
docker volume create my-vol
```

That's it. No size, no path, no driver — Docker picks everything.

### Step 2 — Inspect it

```bash
docker volume inspect my-vol
```

```json
[
  {
    "CreatedAt": "2026-...",
    "Driver": "local",
    "Labels": {},
    "Mountpoint": "/var/lib/docker/volumes/my-vol/_data",
    "Name": "my-vol",
    "Options": {},
    "Scope": "local"
  }
]
```

**`"Driver": "local"`** — exactly what the diagram predicted: `local` is the default volume driver.

**`Mountpoint`** — the volume's real location **on the host**: `/var/lib/docker/volumes/<name>/_data`.

### Step 3 — Mount the volume into a container

```bash
docker run -d --name my-container-1 -v my-vol:/app my-image
```

Breaking down the flags:

| Flag | Meaning |
|---|---|
| `-d` | **detached** — run in the background |
| `--name my-container-1` | name the container |
| `-v my-vol:/app` | **volume** `my-vol` → container path `/app` |
| `my-image` | the image built in Section 5 |

### The `-v` format — host first, container second

```
-v <host-path-or-volume> : <container-path>
```

**This mirrors `-p` for ports** (from Day 03):

```
-p <host-port> : <container-port>
```

> **Host/volume first, container second.** Always. Getting this backwards is a classic error.

### Why `/app`?

Because `/app` is the image's **`WORKDIR`** — the directory where `app.py` was copied. That's "where all the action is happening."

### Step 4 — Exec in and write data

```bash
docker exec -it my-container-1 bash
```

- You land **directly in `/app`** — because `WORKDIR /app` makes it the default directory when you log in.
- `ls` → shows `app.py`.

Now create a file:

```bash
echo "this is my delta data" > file.ext
cat file.ext
# this is my delta data
```

> "delta" = the writable layer. This is the data we're about to prove survives the container.

### Step 5 — Destroy the container

```bash
docker rm -f my-container-1
```

- `-f` is required because the container is **running** (a running container can't be removed without `-f`).
- The container is **gone**.

### Step 6 — The `/var/lib/docker` trap (Docker Desktop)

Where does the volume actually live? On the host, at:

```
/var/lib/docker/volumes/my-vol/_data
```

So let's go there:

```bash
cd /var/lib/docker/volumes
# No such file or directory
```

**Why?** Because this is a **Mac** (or Windows) machine:

- Docker Desktop runs the engine inside a **small Linux VM** (Section 7).
- `/var/lib/docker/...` exists **inside that VM**, not on your Mac's filesystem.
- Accessing the path from the host **cannot work**.

**Two ways around it:**

1. **Log into the Docker Desktop VM**, then `cd /var/lib/docker/volumes/my-vol/_data`.
   ```bash
   docker run -it --rm --privileged --pid=host alpine nsenter -t 1 -m -u -i -n sh
   ```
2. **Mount the same volume into another container** and look there. ← the demo takes this route.

> On a **native Linux** host, `/var/lib/docker/volumes` would simply work.

### Step 7 — Prove persistence

```bash
docker run -it --rm -v my-vol:/app alpine sh
```

| Flag | Meaning |
|---|---|
| `-it` | interactive + TTY |
| `--rm` | **delete this container when the command finishes** |
| `-v my-vol:/app` | the **same volume**, mounted again |
| `alpine` | a tiny throwaway image (different from `my-image`) |
| `sh` | the shell to run |

Inside:

```sh
ls           # app, plus whatever else
cd /app
ls           # file.ext  ← IT SURVIVED
cat file.ext # this is my delta data
```

**The proof.** The original container is deleted, the new container uses a **completely different image** — and the data is still there.

That's exactly what a volume is for:

> **Any container that mounts this volume can store persistent data in it. Even when the container goes away, the data stays safe.**

### Step 8 — Cleanup and a note on `kind`

```bash
exit          # container auto-deletes (--rm)
docker ps     # no containers from the demo
```

But `docker ps` still shows **three running containers** — those are the **kind** cluster:

- 1 container = **control plane** node
- 2 containers = **worker nodes**

> Nice side-observation: your whole Kubernetes cluster is just Docker containers on Docker Desktop.

---

## 9) Types of Docker Volumes

Three types. Know the difference, and know which one production uses.

### 1. Named volume — the default and the production choice

```bash
docker volume create my-vol
docker run -d -v my-vol:/app my-image
```

- **Docker-managed**: Docker decides where it lives (`/var/lib/docker/volumes/...`).
- **This is the default** Docker volume type.
- **If you use volumes in production, you use named volumes.**

**You don't have to create it first.** This single command works too:

```bash
docker run -d -v my-vol:/app my-image
```

> Behind the scenes, Docker **automatically creates** `my-vol` for you. `docker volume create` just makes it explicit/scriptable.

### 2. Bind mount — a host directory, mapped in

```bash
docker run -d -v /host/path:/container/path my-image
```

- Mounts a **specific host directory** into the container.
- **Permission caveat:** the container needs **appropriate permissions** on that host directory — otherwise reads, writes, and executions fail.
- Because it is **tied to a host path**, it can cause **permission issues** and is **less portable** than a named volume.

**When to use it:** config files, local development with live code reload, anything where you *want* the host's actual files.

### 3. tmpfs — a volume backed by RAM

```bash
docker run -d --tmpfs /app my-image
```

- Backed by **memory (RAM)**, not disk.
- **Very fast** — no disk I/O.
- **Data is lost** when the container restarts or is removed.
- If the **host reboots**, the container is down and the data is **gone**.

**Use with caution** — perfect for scratch/cache/temp files, fatal for anything that must persist.

### Comparison

| | **Named volume** | **Bind mount** | **tmpfs** |
|---|---|---|---|
| **Location** | Docker-managed | Your chosen host path | **RAM** |
| **Survives container deletion** | **Yes** | Yes | **No** |
| **Survives host reboot** | Yes | Yes | **No** |
| **Speed** | Normal | Normal | **Fastest** |
| **Permissions** | Docker handles | **You must handle** | Docker handles |
| **When to use** | **Production persistence** | Host files, dev | Scratch / cache |

---

## 10) Docker Concepts → Kubernetes Preview

The lecture repeatedly points forward. Here's the mapping to expect on Day 25:

| Docker concept | Kubernetes analogue | Notes |
|---|---|---|
| Writable layer (ephemeral) | Container filesystem (`emptyDir` for shared scratch) | Dies with the pod |
| **Storage driver** (`overlay2`) | **CRI** → container runtime → storage driver | Same mechanism, one more layer |
| **Volume driver** (`local`, AWS…) | **CSI plugins** | Container Storage Interface |
| **Named volume** | **PersistentVolume + PersistentVolumeClaim** | PVC = a "claim" for a PV |
| Bind mount | `hostPath` (and partly `emptyDir`) | Same portability caveats |
| tmpfs | `emptyDir` with `medium: Memory` | RAM-backed |

---

## 11) Key Takeaways

1. **Containers are ephemeral** — delete the container and the writable layer is gone. Volumes exist to fix exactly that.
2. **Images are shared between containers and are read-only** — three containers from one 50 MB image consume **50 MB**, not 150 MB.
3. **Writes go to a per-container writable layer** (the "delta"), stacked on the shared read-only image.
4. **Layer-creating instructions:** `FROM`, `RUN`, `COPY`, `ADD` — they generate data / modify the filesystem.
5. **Non-layer-creating (metadata):** `WORKDIR`, `EXPOSE`, `CMD`, `ENV`, `LABEL`, `USER` — no storage cost.
6. **More layer-creating work → bigger image.** Use **multi-stage builds** (Day 05) to keep only runtime artifacts in the final image.
7. **`docker history <image>`** proves which instructions consume space — and is your image-size debugging tool.
8. **Storage driver** = container's **ephemeral** internal data; builds the writable layers. `overlay2` is the default on Linux; check with `docker info`.
9. **Volume driver** = **external persistent** data; independent of container lifecycle. `local` is the default.
10. **You need both** — containers still produce scratch data that shouldn't be persisted.
11. **Kubernetes uses CRI** to reach the storage driver, and **CSI plugins** in place of volume drivers (Day 25).
12. **Docker Engine runs only on Linux** because it depends on kernel features: **cgroups** and **network namespaces**.
13. **Docker Desktop** = Engine + Compose + GUI, running inside a **lightweight Linux VM** (Apple Virtualization Framework on macOS, **WSL 2** on Windows).
14. **Consequence:** `/var/lib/docker/...` is **inside that VM** — you can't `cd` to it from the host. Either `nsenter` into the VM or mount the volume into another container to inspect it.
15. **`-v <volume>:<container-path>`** — **host/volume first, container second**, same order as `-p`.
16. **Named volumes are the production choice** and are **auto-created** if you reference a missing name.
17. **Bind mounts** tie you to a host path → **permission issues**; **tmpfs** is RAM-backed → **fast but volatile**.

---

## 12) Essential Commands

```bash
# --- Inspecting the storage stack ---
docker info | Select-String -Pattern "Storage Driver"    # e.g. overlay2
docker history my-image        # layer sizes per instruction

# --- Volumes ---
docker volume create my-vol
docker volume inspect my-vol   # Driver: local, Mountpoint
docker volume ls
docker volume rm my-vol        # only works when not in use

# --- Run with a named volume ---
docker run -d --name my-container-1 -v my-vol:/app my-image
docker exec -it my-container-1 bash

# --- Run with a host bind mount ---
docker run -d -v /host/data:/app my-image

# --- Run with tmpfs (RAM) ---
docker run -d --tmpfs /app my-image

# --- Prove persistence ---
docker rm -f my-container-1
docker run -it --rm -v my-vol:/app alpine sh
#   ls /app  → data still there

# --- Inspect the volume from the Docker Desktop VM (macOS/Windows) ---
docker run -it --rm --privileged --pid=host alpine nsenter -t 1 -m -u -i -n sh
#   then: cd /var/lib/docker/volumes/my-vol/_data
```

---

## 13) Quick Self-Check

1. Why does a container lose its data when it is deleted?
2. Three containers run from one 50 MB image and write 4 MB, 10 MB, 6 MB. What is the total disk consumption, and why?
3. Which Dockerfile instructions create layers, and which don't? What distinguishes them?
4. Why is `FROM` layer-creating but `WORKDIR` is not?
5. How do multi-stage builds reduce image size?
6. What does `docker history` show you, and how do you use it?
7. What is the "writable layer" and why is it called a delta?
8. Storage driver vs volume driver — one sentence each.
9. Which command tells you your storage driver, and what's the Linux default?
10. Why can't Docker Engine be installed directly on macOS or Windows?
11. What does Docker Desktop actually run, and via what on macOS and Windows?
12. Why does `cd /var/lib/docker/volumes` fail on your Mac, and what are your two workarounds?
13. In `-v my-vol:/app`, which side is the volume and which is the container path?
14. Do you have to run `docker volume create` before `docker run -v my-vol:/app`? Why?
15. Name the three volume types and which one production uses.
16. Which volume type loses data on container restart, and why would you ever use it?
17. What are the Kubernetes equivalents of the storage driver, the volume driver, and a named volume?

---

## What's Next (Day 25)

- **Kubernetes core & extended architecture** — modular design, and the three plugin interfaces: **CRI**, **CNI**, **CSI** (where CSI replaces Docker's volume drivers).
- **Kubernetes volumes** follow after that (Day 26).

---

*End of Day 24 notes.*
