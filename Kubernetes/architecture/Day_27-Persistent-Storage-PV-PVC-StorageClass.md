# Persistent Storage in Kubernetes — PV, PVC & StorageClass — Complete Notes (Day 27)

> Source: Day 27 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Persistent storage end to end — **in-tree → CSI**, `hostPath`, **PersistentVolumes**, **PersistentVolumeClaims**, **access modes**, **reclaim policies**, **volume modes**, **StorageClasses**, and **volumeBindingMode**.
> Prerequisite: Day 24 (storage drivers vs volume drivers), Day 25 (CRI/CNI/CSI), Day 26 (`emptyDir`, downwardAPI).

---

## 1) What Is Persistent Storage?

> **Anything that prevails irrespective of the lifetime of the pod.**

The USB-drive analogy: connect a USB drive to your laptop; if the laptop crashes, **the data on the drive survives**. Same for a pod: attach a volume from an **external storage system** and the volume outlives the pod.

### Ephemeral vs persistent — the recap

| | Ephemeral (Day 26) | **Persistent (today)** |
|---|---|---|
| Lifetime | The **pod** | **Independent** of the pod |
| Examples | `emptyDir`, `downwardAPI` | `hostPath`, PV/PVC, cloud disks, NFS |
| Real workloads | Scratch, cache | **Databases, CMS, stateful apps** |

> The framing for today: most real applications need **long-term durable storage** for **stateful workloads** — databases, content management systems.

---

## 2) The Evolution: In-Tree Drivers → CSI

### Where we're coming from (Day 25)

Kubernetes core = **container orchestration**. Networking, storage, and container creation are **not** core — they live behind interfaces:

- **CNI** → networking
- **CRI** → container runtime
- **CSI** → **storage** ← today's subject

The community **sets the standards**; anyone who adheres can write a plugin. The community itself is governed by **CNCF** (hence Kubernetes, Prometheus, Istio, Envoy, **etcd**, **Helm**, **CoreDNS** are all CNCF projects).

### The old world: in-tree drivers

Historically, **storage drivers were embedded in the Kubernetes core**. There was **no CSI**.

**The problem:** Kubernetes can't possibly maintain drivers for **every storage vendor** — NetApp, Dell EMC, plus every cloud.

And even if **AWS wrote its own in-tree driver**:

1. It still had to be **integrated into Kubernetes core**.
2. For anyone to *use* it, there had to be a **Kubernetes upgrade**.

So every new vendor, new feature, or bug fix in a driver meant:

> **Upgrade the entire Kubernetes version.** ❌

That's not how you want to ship software. Vendors should move **independently** of core.

### The modern world: CSI

Now:

> Amazon ships a **new CSI driver version** with **volume expansion** → you **upgrade the CSI driver** → you get volume expansion. **No Kubernetes upgrade.**

| | **In-tree** | **CSI** |
|---|---|---|
| Where it lives | **Inside** Kubernetes core | **Outside**, as a plugin |
| Upgrade to get a new feature | **Whole cluster upgrade** | **Driver upgrade only** |
| Who develops it | Kubernetes community | **Storage vendors + the community around that driver** |
| Status | **Deprecated** | **The standard** |
| If you have the choice | — | **Always choose CSI** |

> **Key clarification:** the *storage systems* (EBS, GCP PD) are **not** deprecated — only the **in-tree way of accessing them**. `awsElasticBlockStore` is deprecated; `csi.ebs.aws.com` is the replacement.

### How to tell which one you're using

Check the **`provisioner`** field in the **StorageClass**, or the **`csi`**/driver field in the PV:

| Backend | What you see |
|---|---|
| **In-tree** | `awsElasticBlockStore` / `kubernetes.io/aws-ebs` — the vendor's name written directly |
| **CSI** | a `csi:` block with something like **`ebs.csi.aws.com`** |

```bash
kubectl get csidrivers              # what CSI drivers are installed
kubectl get sc
kubectl get pv <name> -o yaml       # look for the csi: block
```

**In the docs** (`kubernetes.io/docs` → Volumes), the storage list marks them explicitly:

```
awsElasticBlockStore   deprecated
gcePersistentDisk      deprecated
...                    deprecated
CSI                    ← the current mechanism
```

---

## 3) CSI in Practice: File, Block, and Object Storage

### File storage — mounted by **many** systems

> **File storage is something you mount onto multiple Linux systems.**

10 applications need a **common file share** → file storage lets all of them read **and write** the same share.

### Block storage — typically **one** system

> **Block storage is typically accessed by a single system.**

The laptop-USB-drive picture again: the drive is **private to your laptop**.

> "Typically" and "usually" because corner cases exist (a file share used by one system; block storage attached to multiple). But the **general rule** holds.

| | **File** | **Block** |
|---|---|---|
| Access | **Many systems** | **Typically one** |
| Use cases | **Shared workloads** — web servers reading a common share | **Databases, transactional systems** |
| AWS example | **EFS**, **FSX** | **EBS** |

### CSI drivers exist for both — and not just on cloud

Do **not** assume CSI == cloud only. There are CSI drivers for **on-premises** deployments too, for **both** file and block:

| Driver | Where |
|---|---|
| **AWS EBS CSI** | Block, AWS |
| **AWS EFS / FSX CSI** | File, AWS |
| **GCP Persistent Disk CSI** | Block, GCP |
| **vSAN CSI** | On-prem, **Broadcom/VMware** ecosystem |
| **Portworx CSI** | On-prem |
| **NetApp / Dell EMC** | Their own CSI drivers, both file and block |

### Object storage — the exception

> **Object storage is not supposed to be mounted.**

- Object storage (S3 and friends) has a **flat architecture**; you access objects via **URLs / REST**.
- **File and block can be mounted. Object cannot.**

So how do pods use it?

1. The **pod makes API calls** to the object store, or
2. The application uses the vendor's **SDK** (e.g. the **AWS SDK** for S3), configured alongside your app.

> No PV/PVC mount involved — it's an **application-integration** pattern, not a storage-driver pattern.

### Summary of this section

> Kubernetes used to have many **in-tree** drivers. Today the ecosystem has **fully moved to CSI**, which is the **future-proof** way to provision and consume persistent storage.
> AWS EBS, NFS, iSCSI, Fibre Channel — if you're doing it **the modern way, you're doing it with a CSI driver**.

---

## 4) `hostPath` — Persistent, but a Special Case

### What it is

> **Mounts host node files or directories directly into the pod.**

A directory (or file) that exists **on the node** is shared with the containers in the pod.

### Why it's a special case

- **`hostPath` uses in-tree drivers — there are no CSI drivers for `hostPath`.**
- Persistent in the sense that it outlives the pod — it maps to a real path on the node's filesystem.

### Why Kubernetes does **not** recommend it

**Security.**

> You're creating a directory on the node and sharing it with a pod. If that pod is **malicious**, it can do things in that directory that are **not permitted**.

The official docs warn explicitly: *"Using the hostPath volume type presents many security risks. If you can avoid using a hostPath volume, you should."*

**Where it's acceptable:**

- **Testing**
- Environments with **tight controls** — only the specific permissions that are needed

> But know that Kubernetes **does not recommend `hostPath` in production-grade environments**.

### The `type` field

```yaml
  volumes:
    - name: host-volume
      hostPath:
        path: /host-file
        type: FileOrCreate
```

| `type` | Behaviour |
|---|---|
| *(empty — default)* | No checks performed before mounting |
| **`FileOrCreate`** | If the file doesn't exist, **create** it |
| **`File`** | File must already exist |
| **`DirectoryOrCreate`** | If the directory doesn't exist, **create** it |
| **`Directory`** | Directory must already exist |
| `Socket`, `CharDevice`, `BlockDevice` | For special node-level device files |

> `FileOrCreate` vs `File` is the difference between "make it if missing" and "fail if missing."

### Properties

| Property | Detail |
|---|---|
| **Persists beyond the pod** | Because it maps to a **node path** — deleting the pod doesn't touch the node's disk |
| **Shared between containers in a pod** | Same as `emptyDir` — mount it into each |
| ****Also shared across pods on the same node**** | ← the big difference from `emptyDir` |
| **Not shared across nodes** | The data physically lives on **one** node |

```
emptyDir :  pod-scoped      →  containers in THIS pod only
hostPath :  node-scoped     →  any pod scheduled on THIS node
```

> If a `hostPath` volume is created on **worker-1**, then **any pod on worker-1** can reach it. A pod on **worker-2** cannot.

### Use cases

1. **Scratch space** — temporary storage for pods.
2. **Caching** — node-local storage is usually **fast**.
3. **Host logs** — niche but real: map the node's **log directory** into a pod so the pod can read **host-level logs**.

---

## 5) Demo — `hostPath`

### The manifest

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-example
spec:
  nodeName: kind-worker2            # added for demo 2
  volumes:
    - name: host-volume
      hostPath:
        path: /host-file            # path ON THE NODE
        type: FileOrCreate
  containers:
    - name: busybox
      image: busybox
      command: ["sh", "-c", "sleep 3600"]
      volumeMounts:
        - name: host-volume
          mountPath: /data          # path INSIDE the container
```

Two things to notice:

- **No separate object is created.** `hostPath` (like `emptyDir`) is declared **inside the pod manifest** — there is no "PersistentVolume" here.
- The volume is only **declared**; it must still be **mounted**.

### Step-by-step

```bash
kubectl apply -f hostpath.yaml
kubectl get pods
kubectl get pods -o wide          # note which node (worker-2)
```

### Inside the pod — write to the node's file

```bash
kubectl exec -it hostpath-example -- sh

# inside:
ls                                # shows: data
vi /data                          # /data IS the node's /host-file
# insert: this is my file, do not touch it
cat /data
# this is my file, do not touch it
```

> Because we mapped a **file**, the mount path `/data` **is** that file — not a directory containing it. That's why `ls` shows `data` as a single entry and `vi /data` edits it directly.

### Proving node-scoping

Create a **second pod** on the **same node** (`nodeName: kind-worker2`), same volume and mount:

```bash
kubectl apply -f hostpath.yaml            # now pod 2, nodeName: kind-worker2
kubectl exec hostpath-example-2 -- cat /data
# this is my file, do not touch it        ← SHARED, same node
```

Create a **third pod** on a **different node** (`nodeName: kind-worker`):

```bash
kubectl exec hostpath-example-3 -- cat /data
# (nothing / error)                       ← NOT shared, different node
```

**Why?** The file lives on **worker-2's** filesystem. Pod 3 is on **worker-1**, so it sees its own filesystem — where that file does not exist.

### What "node storage" means here (kind + Docker Desktop)

This is the nuance the instructor stresses:

```
macOS / Windows
   └── Docker Desktop
         └── lightweight Linux VM
               └── Docker Engine
                     ├── kind-control-plane   (container = a "node")
                     ├── kind-worker          (container = a "node")
                     └── kind-worker2         (container = a "node")
```

- Cluster nodes are **containers** (kind = Kubernetes **in** Docker).
- The **"host" storage for a pod** is the storage of **the node container it runs on**.
- Those node containers indirectly use the **Linux VM's** storage, which sits on **macOS storage**.

| Setup | What "host storage" means |
|---|---|
| **Ubuntu with Docker Engine** | The **actual host** filesystem |
| **macOS/Windows + Docker Desktop** | The **node container's** filesystem (inside the Docker Desktop Linux VM) |
| **EC2 worker node** | The **EC2 instance's** storage |

> Practically: `hostPath` on kind gives you a directory **inside a node container**, not on your Mac.

### Cleanup

```bash
kubectl delete pods hostpath-example hostpath-example-2 hostpath-example-3 --force
```

---

## 6) PV & PVC — The Core Abstraction

### The diagram, in words

```
Physical storage  ──►  PV  ──►  PVC  ──►  Pod  ──►  containers (mount)
   (5 GB)          (logical)  (claim)
```

| Object | What it is |
|---|---|
| **PV (PersistentVolume)** | A **logical abstraction of the physical volume** — a cluster resource representing, say, **5 GB** |
| **PVC (PersistentVolumeClaim)** | A **claim** on a PV — "I want 2 GB with this access mode" |
| **Pod** | References the **PVC** as a volume; containers mount it |

### The binding rule

> **PV : PVC = 1 : 1.** Only **one** PVC can claim a given PV, and a PV serves **one** PVC.

### The node analogy (the clearest way to hold this)

| Scheduling a pod | Claiming storage |
|---|---|
| Pod requests **1 vCPU + 4 GB** | PVC requests **2 GB** |
| **Node** provides those resources | **PV** provides that capacity |
| Pod consumes node capacity | PVC consumes PV capacity |

A PVC's `requests.storage` is satisfied by a PV of **equal or greater** size — just as a pod fits on any node with enough capacity.

### The full workflow (roles)

```
Developer:    "I need 5 GB of persistent storage for my app."
   │
   ▼
K8s Admin:    coordinates with the storage admin
   │
   ▼
Storage Admin: creates a 5 GB volume on the physical storage
   │
   ▼
K8s Admin:    creates a PV of 5 GB        (CSI plugin lets the cluster talk to the storage)
   │
   ▼
Admin / Dev:  creates the PVC
   │
   ▼
Developer:    references the PVC in the pod spec (spec.volumes)
   │
   ▼
Developer:    mounts the volume into one container — or all of them
```

**Role overlap is normal.** In many environments the Kubernetes admin does everything end to end; in others **developers** create their own pods and **PVCs** while admins only handle **PVs**. And with **StorageClasses** (Section 10), even the PV creation gets automated away.

### Namespacing — where the split matters

```bash
kubectl api-resources        # shows NAMESPACED true/false
```

| Object | Namespaced? | Meaning |
|---|---|---|
| **PersistentVolume** | **false** | **Cluster-wide** — like **nodes** |
| **PersistentVolumeClaim** | **true** | Scoped to a namespace |
| **Pod** | **true** | Scoped to a namespace |

**Consequences:**

- A PVC lives in **one namespace** and is bound to a PV.
- **Pods in the same namespace** can use that PVC.
- **Pods in another namespace cannot** — even if the PV is cluster-wide, the **claim** isn't.
- Multiple pods **within** the namespace can share the PVC (subject to access modes).
- And because of **1:1 binding**, a second PVC cannot claim that same PV — even if it wants the same 5 GB.

---

## 7) Access Modes

> **Access modes govern how the volume is mounted *across nodes*.** Think **worker nodes — not pods.**

| Mode | Short | Meaning |
|---|---|---|
| **ReadWriteOnce** | **RWO** | Mounted **read-write by a single node**. Multiple pods **on that node** can use it |
| **ReadWriteOncePod** | **RWOP** | Only a **single pod** may access it. **Introduced in 1.29** (course runs **1.32**) |
| **ReadOnlyMany** | **ROX** | Mounted **read-only by many nodes** simultaneously |
| **ReadWriteMany** | **RWX** | Mounted **read-write by many nodes** simultaneously |

### The memory hook

> **`Once` → think BLOCK storage. `Many` → think FILE storage.**

| If you have… | Use | Because |
|---|---|---|
| **Block storage** (databases, high-transaction systems) | **RWO** | Block storage is meant for a **single system** |
| **File storage** (shared workloads) | **RWX** / **ROX** | File storage is meant for **many systems** |

### Example 1 — PV + PVC with access modes

**PV (`pv.yaml`):**

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: example-pv
spec:
  capacity:
    storage: 5Gi                # storage admin gave us 5 GB
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""          # no storage class
  hostPath:
    path: /mnt/data             # in real life: an EBS/EFS/vSphere handle
```

**PVC (`pvc.yaml`):**

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: example-pvc
spec:
  accessModes:
    - ReadWriteOnce             # MUST match the PV
  resources:
    requests:
      storage: 2Gi              # requesting less than 5Gi — fine
  storageClassName: ""
```

**Pod (`pod.yaml`):**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: example-pod
spec:
  containers:
    - name: app
      image: nginx
      volumeMounts:
        - name: persistent-storage
          mountPath: /usr/share/nginx/html
  volumes:
    - name: persistent-storage
      persistentVolumeClaim:
        claimName: example-pvc      # ← the PVC, by name
```

### Why this binds

| Condition | PV | PVC |
|---|---|---|
| **Access mode** | `ReadWriteOnce` | `ReadWriteOnce` ✅ |
| **Capacity** | 5Gi **≥** | 2Gi ✅ |
| **Storage class** | `""` | `""` ✅ |

> **PV capacity must be equal to or greater than the PVC's request.** A 2 Gi request **binds** to a 5 Gi PV.

And then — the subtle part:

> **The PVC reports the PV's capacity (5Gi), not what it asked for (2Gi).**

Very easy to get wrong in an exam.

---

## 8) Volume Mode

> **`volumeMode` decides how the volume is *presented* to the container.**

| Mode | Behaviour |
|---|---|
| **`Filesystem`** (default) | Kubernetes **formats** the volume with a filesystem (e.g. **`ext4`**) before the container sees it |
| **`Block`** | Volume is presented **raw, with no filesystem** — the container formats it however it wants |

**The VMware analogy:** raw device mappings (**RDMs**) were presented **directly to the OS**, not formatted with VMFS — the OS formatted them itself. `volumeMode: Block` is the same idea.

**Who wants Block?** Some **Oracle and other databases** — anything that insists on managing its own on-disk layout.

> Don't confuse **`volumeMode: Block`** with **block storage**. They're different axes: *block storage* is about how the backend is exposed; `volumeMode: Block` is about *whether Kubernetes formats it*.

**`volumeMode` must match between PV and PVC** for binding to succeed.

---

## 9) Reclaim Policies

> **The reclaim policy defines what happens to the physical volume when the PVC is deleted.**

| Policy | Behaviour | When to use |
|---|---|---|
| **`Delete`** | PVC deleted → **PV and the underlying physical volume are deleted** | **Cloud** (you pay per GB!), and **dynamically provisioned** storage — the common default |
| **`Retain`** | PVC deleted → **PV and data remain** | **Auditing**, preserving data, manual/administered storage |
| **`Recycle`** | ~~`rm -rf` the volume's data~~ | **Deprecated** — use `Delete` or `Retain` instead |

### Delete — the cloud default

In cloud Kubernetes, `Delete` is what you'll usually see:

> When you delete the pod and the PVC, you also want the **PV gone** — because an **EBS volume costs money** for as long as it exists.

**Also common for dynamically provisioned storage** (Section 10).

### Retain — the careful choice

- Delete the PVC → **the PV survives** (status becomes `Released`, and it still holds the data).
- Common with **`hostPath`** and **file storage**: several pods may have been reading that share; you don't want a PVC deletion to wipe it.
- Also used when you might **recreate a PVC** and give other pods access to the **same data**.

> The demo's PV uses `Retain` because it's `hostPath`-backed and standing in for a file share.
> But note: for **block storage** — cloud *or* on-prem — the instructor has often seen admins use **`Delete`**.

### Recycle — gone

Old behaviour: essentially run `rm -rf` on the volume. Modern practice replaces it with **Delete** (then recreate) or **Retain** — so it's deprecated.

---

## 10) The AWS Example — Full PV Anatomy

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ebs-csi-pv
spec:
  capacity:
    storage: 10Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Delete
  storageClassName: ebs-sc
  csi:
    driver: ebs.csi.aws.com
    volumeHandle: vol-0123456789abcdef0    # the REAL EBS volume ID
    fsType: ext4
```

| Field | Meaning |
|---|---|
| `capacity.storage` | 10 Gi — and a **10 Gi EBS volume** was actually created |
| `volumeMode` | `Filesystem` → formatted **ext4** before the container sees it |
| `accessModes` | `ReadWriteOnce` — block storage, single node |
| `persistentVolumeReclaimPolicy` | `Delete` — typical for cloud block storage |
| `storageClassName` | `ebs-sc` — ties the PV to a class |
| **`csi.driver`** | **`ebs.csi.aws.com`** → **CSI-backed**, not in-tree |
| **`csi.volumeHandle`** | The **actual AWS volume ID** — the bridge between Kubernetes and the cloud |
| `csi.fsType` | `ext4` |

**Matching PVC:**

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ebs-csi-pvc
spec:
  accessModes:
    - ReadWriteOnce          # must match
  volumeMode: Filesystem     # must match
  resources:
    requests:
      storage: 10Gi
  storageClassName: ebs-sc   # must match
  volumeName: ebs-csi-pv     # optional: bind to THIS PV only
```

**`volumeName` is a hard constraint.** If you specify a PV that doesn't exist, the PVC stays **`Pending`** — it will not fall back to any other volume.

`storageClassName: ""` (empty string, not omitted) explicitly means **"no storage class"**.

---

## 11) Demo — PV & PVC by Hand

### Step 0 — Clear the way (back up and delete the default StorageClass)

```bash
kubectl get sc
kubectl get sc -o yaml > sc.yaml      # BACK IT UP — we'll re-create it later
kubectl delete sc standard
kubectl get sc                        # now empty
```

We delete it so the PV/PVC binding is **manual** — proving how binding works before automating it.

### Step 1 — Create the PV

```bash
kubectl apply -f pv.yaml
kubectl get pv
```

```
NAME         CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM   STORAGECLASS
example-pv   5Gi        RWO            Retain           Available           ...
```

- **`Available`** = created but **not claimed** yet.
- `CLAIM` is blank, `STORAGECLASS` is blank.

```bash
kubectl describe pv example-pv     # shows source (hostPath in this demo), status, claim
```

### Step 2 — Create the PVC

```bash
kubectl apply -f pvc.yaml
kubectl get pvc
```

```
NAME          STATUS   VOLUME       CAPACITY   ACCESS MODES   STORAGECLASS
example-pvc   Bound    example-pv   5Gi        RWO
```

- **`Bound`** — it found the PV.
- **`CAPACITY: 5Gi`** — *not* the 2Gi we requested. **The PV's size wins.**
- Note `STORAGECLASS` blank on both.

```bash
kubectl get pv
# STATUS changed: Available → Bound
```

### Step 3 — Prove the ordering matters (the "failed binding" event)

```bash
kubectl delete pvc example-pvc            # with the pod not yet created
kubectl delete pv example-pv

kubectl apply -f pvc.yaml                 # PVC FIRST
kubectl get pvc
```

```
example-pvc   Pending   ...   <no capacity>
```

```bash
kubectl describe pvc example-pvc
```

```
Events:
  Warning  ProvisioningFailed  failed to provision volume...
  ...
```

Now create the PV:

```bash
kubectl apply -f pv.yaml
kubectl get pvc            # Pending → Bound (retroactively)
```

> **Binding is asynchronous.** A PVC that can't find a PV waits in `Pending` and binds **as soon as a suitable PV appears**. The `failed binding` event is a snapshot in time — not a permanent error.

### Step 4 — Consume it from a pod

```bash
kubectl apply -f pod.yaml
kubectl describe pod example-pod
```

```
Mounts:
  /usr/share/nginx/html from persistent-storage (rw)
Conditions: Ready True
```

**The whole chain, connected:**

```
PV (5Gi)  →  PVC (claims it)  →  Pod's spec.volumes.persistentVolumeClaim  →  container volumeMounts
```

> Same foundation as `emptyDir`: **give the volume to the pod, then mount it into containers.** Only the *type* changed.

### Step 5 — The deletion-order protection (a real gotcha)

Try deleting the PV while everything is in use:

```bash
kubectl delete pv example-pv
# command hangs...
```

In another terminal:

```bash
kubectl get pv
# example-pv   ...   Terminating

kubectl get pvc
# example-pvc  Bound

kubectl describe pod example-pod
# still has the mount
```

Deleting the PVC too doesn't help:

```bash
kubectl delete pvc example-pvc      # terminating
kubectl get pv; kubectl get pvc      # both Terminating, neither gone
```

**Why?** Kubernetes **protects** storage objects in use:

> - You **cannot delete a PVC while a pod is using it.**
> - You **cannot delete a PV while a PVC is bounding it.**

**The correct deletion order:**

```
1. delete the POD
2. delete the PVC
3. delete the PV
```

```bash
kubectl delete pod example-pod
# → PV deletion completes, PVC deletion completes
kubectl get pv     # empty
kubectl get pvc    # empty
```

> This is a **protection mechanism** — finalizers (`kubernetes.io/pvc-protection`, `kubernetes.io/pv-protection`) hold the object in `Terminating` until nothing references it. Skipping the order is the single most common reason "delete hangs".

---

## 12) StorageClasses — Automation

### The problem the instructor names directly

> *"Every time someone wanted storage, I was disturbed, and I was not liking that."*

As a Kubernetes administrator you **don't want to create PVs all day**. Storage requests **grow with the cluster and the applications**. So:

> **Whenever a PVC is created, a corresponding PV must be created automatically.**

That's **dynamic provisioning**.

It's also an organisational fix: as Kubernetes got popular, **developers** started writing their own manifests and deploying apps. **They shouldn't have to trouble administrators** every time they need storage.

### Definition

> **A StorageClass defines different storage configurations, enabling dynamic provisioning of PersistentVolumes.**

### Key design point: no access mode here

> **You do not define `accessModes` in a StorageClass.** Whatever the **PVC** requests is used for the auto-created PV.

### Why multiple StorageClasses?

Real clusters have **storage tiers**:

- **File** vs **block**
- Block with **lower IOPS** vs **higher IOPS**
- File limited to **one availability zone** vs **spanning a region**
- **Gold / platinum** tiers — SSD for app 1, HDD for app 2

Example: two classes both backed by the **EBS CSI driver**, but with different volume types:

- **`gp3`** — general purpose
- **`io1`** — **provisioned IOPS**, higher performance

### The StorageClass YAML (AWS)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-sc-gp3
provisioner: ebs.csi.aws.com         # ← CSI, not in-tree
parameters:
  type: gp3                          # or: io1
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
```

### The PVC that uses it

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ebs-csi-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: ebs-sc-gp3       # ← name the class you want
```

**That's the crucial mechanism:** a cluster can have **many** StorageClasses, and the PVC **picks one by name**. Use `ebs-sc-io1` instead and the auto-created PV would be io1.

### What gets auto-created

```yaml
kind: PersistentVolume
spec:
  accessModes: [ReadWriteOnce]                 # copied from the PVC
  capacity:
    storage: 10Gi
  persistentVolumeReclaimPolicy: Delete        # from the SC
  storageClassName: ebs-sc-gp3                 # from the PVC/SC
  csi:
    driver: ebs.csi.aws.com
    fsType: ext4                               # a class default
    volumeHandle: vol-...                       # newly created EBS volume
```

> **The magic:** access mode and reclaim policy come from the **PVC/SC**, everything else from the **StorageClass's driver + parameters**. The burden of creating PVs is **gone**.

---

## 13) `volumeBindingMode` — Immediate vs WaitForFirstConsumer

### `WaitForFirstConsumer`

> **Only create the PV once the pod that wants the PVC is created.**

So: create a PVC alone, and **no PV is provisioned**. Why?

**Reason 1 — Cost.**

> If no pod is using it, why would you provision a **10 GB EBS volume**? Your cloud provider charges you for those 10 GB regardless.

**Reason 2 — Availability Zone alignment (the important one).**

Consider AWS **Mumbai region** with **two AZs** (`a1`, `a2`):

- An **EC2 instance** belongs to **exactly one AZ** — it cannot span AZs.
- An **EBS volume** is also **AZ-specific**.
- **Nodes and storage are AZ-bound resources.**

Now the failure:

```
PVC created → PV provisioned in a1
Pod scheduled → lands in a2
                 │
                 ▼
        a2 pod cannot mount a1 volume   ❌
```

**With `WaitForFirstConsumer`:**

```
PVC created          → no PV yet
Pod scheduled to a2  → PV created IN a2
                     → binds immediately ✅
```

> The PV is created **in the same AZ as the pod**, because it's only created **after** the pod is scheduled.

### `Immediate`

Provisions the PV **as soon as the PVC is created** — with the AZ misalignment risk above.

### The instructor's preference

> *"I **personally always use `WaitForFirstConsumer`."* — for the cost benefit **and** the AZ alignment.

---

## 14) Demo — Dynamic Provisioning

### The StorageClass (`sc.yaml` from the `standard` backup)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard
provisioner: rancher.io/local-path      # kind's local-path provisioner
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
```

> **`provisioner` is the whole point.** After Day 27 you should read that field reflexively: `rancher.io/local-path` here; in production it would be `ebs.csi.aws.com`.
> **Note:** in production you'd almost always pair a **CSI driver** with a **StorageClass**.

```bash
kubectl apply -f sc.yaml
kubectl get sc
```

### PVC without a pod → stays Pending

```bash
kubectl apply -f pvc.yaml
kubectl get pvc
# example-pvc   Pending
kubectl get pv
# (none)
```

**`Pending` is correct here** — `volumeBindingMode: WaitForFirstConsumer` is doing its job. No pod, no PV.

### Create the pod → PV appears

```bash
kubectl apply -f pvc-pod.yaml
kubectl get pv
# pvc-<uuid>   2Gi   RWO   Delete   Bound   default/example-pvc   standard
```

Three things to notice:

| Observation | Meaning |
|---|---|
| **A PV appeared automatically** | Dynamic provisioning worked |
| **Capacity is 2Gi** | Sized to the **PVC's request** — unlike the manual demo where a 2Gi request got a 5Gi PV |
| **Name is `pvc-<uuid>`** | Generated by the provisioner; no human named it |

```bash
kubectl get pvc          # Bound
kubectl get pods         # Running
kubectl describe pod example-pod
# Mounts: ... from persistent-storage (rw)
```

> *That* is the efficiency win: manual PVs are fixed-size (5Gi for a 2Gi need); dynamic provisioning gives you **exactly what you asked for**.

---

## 15) Binding Conditions — The Checklist

For a PVC to bind to a PV (and for a StorageClass to provision one), **all** of these must hold:

| # | Condition | Notes |
|---|---|---|
| 1 | **`storageClassName` must match** | If the PVC names `ebs-sc-mystorage` and no such class exists, **no PV is created** |
| 2 | **Access mode must match** | PVC `ReadWriteMany` requires a PV with `ReadWriteMany` |
| 3 | **Capacity must be sufficient** | PV capacity **≥** PVC request |
| 4 | **`volumeMode` must match** | `Filesystem` ↔ `Filesystem`, or `Block` ↔ `Block` |
| 5 | **PV must be available** | Status `Available` — not already `Bound` to another PVC (1:1!) |
| 6 | **`volumeName`** (if specified) | Must point to an existing PV; otherwise `Pending` |

> Miss any one and you get `Pending` — the single most common PVC problem. Work the list top to bottom.

---

## 16) Key Takeaways

1. **Persistent storage prevails beyond the pod's lifetime** — required for databases, CMS, stateful workloads.
2. **Storage moved from in-tree drivers to CSI.** In-tree required a **whole Kubernetes upgrade** for any driver change; **CSI drivers upgrade independently**.
3. **Always choose CSI** when both are available. In-tree examples (AWS EBS, GCP PD) are **deprecated** — but the *storage systems* aren't.
4. **Check the provisioner:** in-tree writes the vendor name directly; **CSI** shows `csi:` / `ebs.csi.aws.com`.
5. **File storage = many systems** (EFS, FSX). **Block storage = typically one system** (EBS, databases).
6. **Object storage is not mounted** — access it via API calls or an **SDK** (S3).
7. **`hostPath` uses in-tree drivers** — there is **no CSI for it**, and Kubernetes **does not recommend it** (security risk: a malicious pod can manipulate the node's files).
8. **`hostPath` is node-scoped**: shared by **all pods on the same node**, invisible to pods on other nodes — unlike `emptyDir`, which is pod-scoped.
9. **`hostPath.type`** controls existence checking: `FileOrCreate`, `File`, `DirectoryOrCreate`, `Directory` (+ device/socket types).
10. **PV = logical abstraction of physical storage. PVC = a claim on a PV. Binding is 1:1.**
11. **PV is cluster-scoped; PVC and pods are namespace-scoped.** Pods in another namespace cannot use your PVC.
12. **Access modes are about NODES, not pods:** **RWO** (single node, multiple pods), **RWOP** (single pod, 1.29+), **ROX** (many nodes read-only), **RWX** (many nodes read-write).
13. **`Once` → block storage; `Many` → file storage.**
14. **PV capacity ≥ PVC request** → binds; and the **PVC reports the PV's size**, not the requested size.
15. **`volumeMode`:** `Filesystem` (formatted, e.g. ext4 — default) vs `Block` (raw, container formats it — Oracle-style, like VMware RDMs).
16. **Reclaim policies:** **`Delete`** (cloud/dynamic default — stop paying), **`Retain`** (keep data — audit/hostPath/file), **`Recycle`** (deprecated).
17. **Deletion order: pod → PVC → PV.** You cannot delete a PVC in use by a pod, or a PV bound to a PVC; they hang in `Terminating`.
18. **StorageClass = dynamic provisioning.** Define the driver + parameters (gp3/io1); the PVC names the class; the PV is created for you, **sized to the request**.
19. **`accessModes` are not in the StorageClass** — they're taken from the PVC.
20. **`volumeBindingMode: WaitForFirstConsumer`** delays provisioning until a pod exists — saving cost **and** ensuring the volume lands in the pod's **AZ**. `Immediate` provisions right away.
21. **Binding requires all of:** storage class, access mode, capacity, volume mode, PV availability (and `volumeName` if set).

---

## 17) Essential YAML & Commands

```yaml
# --- Manual PV (hostPath, for the demo) ---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: example-pv
spec:
  capacity:
    storage: 5Gi
  accessModes: ["ReadWriteOnce"]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  hostPath:
    path: /mnt/data

# --- Manual PV (AWS, CSI-backed) ---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ebs-csi-pv
spec:
  capacity: { storage: 10Gi }
  volumeMode: Filesystem
  accessModes: ["ReadWriteOnce"]
  persistentVolumeReclaimPolicy: Delete
  storageClassName: ebs-sc
  csi:
    driver: ebs.csi.aws.com
    volumeHandle: vol-0123456789abcdef0
    fsType: ext4

# --- PVC ---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: example-pvc
spec:
  accessModes: ["ReadWriteOnce"]
  volumeMode: Filesystem
  resources:
    requests:
      storage: 2Gi
  storageClassName: ebs-sc        # "" for no class

# --- Pod consuming a PVC ---
spec:
  containers:
    - name: app
      image: nginx
      volumeMounts:
        - name: persistent-storage
          mountPath: /usr/share/nginx/html
  volumes:
    - name: persistent-storage
      persistentVolumeClaim:
        claimName: example-pvc

# --- StorageClass ---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-sc-gp3
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
```

```bash
# Discover
kubectl api-resources | Select-String -Pattern "persistent|storageclass"
kubectl get csidrivers
kubectl get sc
kubectl get pv
kubectl get pvc

# Inspect
kubectl describe pv <pv>
kubectl describe pvc <pvc>
kubectl get pv <pv> -o yaml

# Back up / remove a StorageClass (demo trick)
kubectl get sc -o yaml > sc.yaml
kubectl delete sc standard

# Correct deletion order
kubectl delete pod <pod>
kubectl delete pvc <pvc>
kubectl delete pv <pv>
```

---

## 18) Quick Self-Check

1. Define persistent storage in one sentence.
2. What was the core problem with **in-tree** storage drivers?
3. In-tree vs CSI: which one requires a Kubernetes upgrade to gain a new driver feature?
4. Are AWS EBS and GCP PD deprecated? Be precise about what *is* deprecated.
5. How do you tell from a StorageClass whether you're CSI-backed or in-tree?
6. File vs block storage — which is designed for many systems, and which for one?
7. Can you mount object storage into a pod? What do you do instead?
8. Why does Kubernetes not recommend `hostPath`?
9. A `hostPath` volume exists on worker-2. Can a pod on worker-1 read it? Why?
10. What are the `hostPath` `type` values, and what does `FileOrCreate` do?
11. Define PV and PVC, and state the binding ratio.
12. Which is cluster-scoped: PV or PVC? What stops another namespace from using your PVC?
13. Name the four access modes and the "once/many → block/file" rule.
14. A PVC requests 2Gi; it binds to a 5Gi PV. What capacity does the PVC report?
15. What's the difference between `volumeMode: Filesystem` and `volumeMode: Block`? What's the VMware analogue?
16. Name the three reclaim policies; which is deprecated, and which is the cloud default?
17. You delete a PV and it hangs at `Terminating`. Why, and what's the fix?
18. What does a StorageClass automate? Where do access modes come from?
19. Why would you have multiple StorageClasses in one cluster?
20. `WaitForFirstConsumer` vs `Immediate` — give both the cost and the AZ reason.
21. List the six binding conditions from memory.
22. In the dynamic-provisioning demo, why was the PVC `Pending` before the pod existed?

---

## What's Next (Day 28)

- **ConfigMaps and Secrets** — injecting configuration and sensitive data into pods, decoupling them from the container image (previewed in Day 26).

---

*End of Day 27 notes.*
