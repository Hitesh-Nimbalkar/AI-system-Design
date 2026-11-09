# Kubernetes Core & Extended Architecture — CRI, CNI, CSI — Complete Notes (Day 25)

> Source: Day 25 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Kubernetes' modular design — what is *core*, what is *pluggable*, and the three plugin interfaces: **CRI**, **CNI**, **CSI**.
> A deliberately "lightweight but crucial" lecture: no demo, pure architecture.
> Prerequisite: Day 07 (control plane / data plane, deployment workflow), Day 08 (Kubernetes + CNCF history), Day 24 (storage drivers vs volume drivers).

---

## 1) The Thesis: Modular by Design

> Kubernetes follows a **highly modular design**. Instead of embedding all functionality into the **core**, it relies on **plugins**, **add-ons**, and **third-party integrations** to extend its capabilities.

**Kubernetes' core purpose is container orchestration. Nothing else.**

It explicitly does **not** care:

- how a container or pod is *created* (that's the container runtime)
- how the underlying *networking* works (that's the CNI)
- how *storage* is attached (that's the CSI)

So Kubernetes said: *"My core does orchestration. Everything else, I outsource — but I define the **standards** you must adhere to."*

> **The contract:** if you implement the standard, you can plug your own system in. The core stays the same; everything else is swappable.

---

## 2) The Decoupling Analogy (the thread running through the whole course)

Kubernetes' architecture is the same idea we've been applying to applications since Day 01.

### The application journey

```
Monolith  →  Frontend + Backend + Database  →  Microservices
```

| Stage | What changed |
|---|---|
| **Monolith** | Everything in one deployable unit |
| **3-tier** | Decoupled into frontend, backend, database |
| **Microservices** | Further split — wishlist, orders, payments, etc., **independent of each other** |

### Why microservices — and why it maps to Kubernetes

- If the **wishlist** service goes down, **orders and payments keep working**.
- **Not the entire application dies at once.** That's the whole point of decoupling.
- Each microservice has **one specific purpose**: the wishlist service only knows how wishlists work — add an item, remove an item. Nothing else.

### The parallel

| Application | Kubernetes |
|---|---|
| Monolith | The old, do-everything orchestrator |
| Microservices | **Core + plugins** |
| "Wishlist down ≠ app down" | "CNI broken ≠ orchestration broken" |
| Each service does one thing | Each plugin does one job, behind a standard interface |

> The instructor's framing: decoupling is the single most repeated idea in the course — and Kubernetes is itself built that way.

---

## 3) What IS Kubernetes Core?

```
┌───────────────────────────────────────────────────────────┐
│                        CORE                               │
│                                                           │
│  CONTROL PLANE                     NODE                   │
│  ┌──────────────────┐              ┌──────────────────┐   │
│  │ API Server       │              │ kubelet          │   │
│  │ Scheduler        │              │ kube-proxy       │   │
│  │ Controller Mgr   │              └──────────────────┘   │
│  │ etcd             │                                     │
│  │ Cloud Ctrl Mgr   │                                     │
│  └──────────────────┘                                     │
└───────────────────────────────────────────────────────────┘
```

### Control plane components

| Component | Critical role (as summarised here) |
|---|---|
| **API Server** | **Entry point** for **intra- and inter-cluster** communication |
| **Scheduler** | **Places workloads onto nodes** |
| **Controller Manager** | Ensures **desired state == current state** |
| **etcd** | The **database** of the cluster |
| **Cloud Controller Manager** | Lets Kubernetes interact with **cloud provider resources** |

**Cloud Controller Manager in practice (AWS example):**

- AWS **Secrets Manager**
- AWS **KMS** (encryption keys)
- **Application Load Balancers**
- …and many more cloud services

> The lecture only names the *critical* roles. For the full deep dive — and a live demonstration of each component's behaviour during a Deployment creation — see **Day 07**.

### Node components

| Component | Role |
|---|---|
| **kubelet** | Asks the container runtime to **create containers**, then **monitors** them — plus a lot more |
| **kube-proxy** | Handles **Service-to-Pod networking** |

That's the whole core. Everything below is *outside* it.

---

## 4) Who Maintains the Core? The Kubernetes Community

**Kubernetes community = passionate developers + DevOps engineers + organizations.**

- People like you and me who are eager about the technology.
- **Organizations**: Google, AWS, Red Hat, Ericsson — all contribute to Kubernetes development.

**The community owns the core:**

- A new feature in the **Deployment** object → the community designs, builds, tests it.
- An update to the **Controller Manager** → the community owns it.

Anything pertaining to those components is the community's responsibility, and therefore **falls under Kubernetes core**.

---

## 5) What Is NOT Core? Three Categories

| Category | Examples | Extends |
|---|---|---|
| **Plugins** | **CRI**, **CNI**, **CSI** | Container runtime, networking, storage |
| **Add-ons** | Ingress controllers, monitoring (New Relic, Prometheus), service meshes | Traffic, observability, service-to-service security |
| **Third-party extensions** | **Helm**, Prometheus, and many more | Packaging, monitoring, everything else |

### Add-ons in detail

| Add-on | Job |
|---|---|
| **Ingress controllers** | Distribute traffic in the cluster; support **host-based** and **path-based routing rules** (covered later in the course) |
| **Monitoring tools** | **New Relic**, **Prometheus**, and many third-party tools |
| **Service meshes** | Define **how microservices within the cluster interact**, and the **security** of that interaction |

> Don't rush these. The instructor's advice: take them as high-level awareness now; the course zooms into each later.

---

## 6) CRI — Container Runtime Interface

### What it is

> **CRI = a set of standards / rules defined by the Kubernetes community** (which works under **CNCF**).

- Any company, person, or project that **adheres to those rules can write its own container runtime**.
- It is an **interface**: Kubernetes says "give me these operations", the runtime implements them.

### Why isn't the container runtime part of core?

Because **container runtime ≠ container orchestration**.

- A runtime **pulls images** and does everything **container-related**.
- Kubernetes core is **orchestration** — deciding *what* runs *where*, keeping desired state.
- Creating containers and securing them is **not** the core's job.

So the runtime sits behind an interface, and Kubernetes never needs to know which one it's talking to.

### CRI plugins (container runtimes)

| Runtime | Character |
|---|---|
| **containerd** | The **default for most setups** — lightweight and optimized. Itself a **CNCF project**, developed by the Kubernetes community |
| **CRI-O** (pronounced "cry-oh") | Designed for **OpenShift**; tightly integrates with Kubernetes |
| **Podman** | Daemonless runtime |
| **Kata Containers** | **Hardware isolation** for better security |
| **gVisor** | Google's; **user-space sandboxing** for **untrusted workloads** |

### "If containerd is by the community, why not make it THE default?"

Because **every project and application has its own requirements** — you cannot force one runtime on everyone:

- Need lightweight and standard → **containerd**.
- Need **OpenShift** → **CRI-O**. (OpenShift is itself a **Kubernetes distribution** by **Red Hat** — like **EKS**, **AKS**, **GKE** — and every OpenShift deployment uses CRI-O.)
- Need **hardware-level isolation** → **Kata Containers**.
- Need to run **untrusted workloads safely** → **gVisor**.

### CRI responsibilities

- **Container lifecycle management**
- **Image management**
- **Logging**
- **Security**

(Not exhaustive — just the main ones.)

---

## 7) CNI — Container Network Interface

### What it is

> **CNI sets the standard** that anyone writing a network plugin must adhere to.

**Kubernetes core's position:** *"I don't care how one pod talks to another. My job is orchestration. To establish pod-to-pod communication — regardless of which node the pods live on — use a CNI."*

### CNI plugins

| Plugin | Character |
|---|---|
| **Calico** | Ideal for **advanced security** and **BGP routing** |
| **AWS VPC CNI** | Native to **Amazon EKS** |
| **Azure CNI** | Native to **AKS** |
| **Cilium** ("Celium") | **High-performance** networking and security (eBPF-based) |
| **Flannel** | **Lightweight** — but **does not support NetworkPolicies** |
| **Weave Net** ("VNET") | **Encrypted** communication between pods |

### CNI responsibilities

- **Pod networking** — how pods speak to each other
- **IP address management (IPAM)**
- **Routing and connectivity** within the cluster
- **Security enforcement** — this is where **NetworkPolicies** come in later: only certain workloads may talk to each other, per your compliance needs

### Why can't there be just ONE CNI?

**Because of requirements — especially cloud providers.**

The big three (**AWS, Google, Microsoft**) each have their **own network tooling**, and it isn't the same. So each needs its own plugin:

- **Amazon EKS** → **AWS VPC CNI**
- **AKS** → **Azure CNI**

### "Can't I use Calico or Cilium on EKS?"

**Yes — it is not mandatory to use AWS VPC CNI.** EKS/AKS/GKE run **vanilla Kubernetes** with extensions on top, and any compliant CNI works.

**But** on a cloud provider, the native CNI gives you **features unavailable elsewhere**:

- **Pod security groups** — available with **AWS VPC CNI**; as far as the instructor knows, no other CNI offers them.
- **Native vendor support** — when you're troubleshooting and stuck, you can use the **cloud provider's support**.

> **Recommendation: use the cloud-native CNI when you're on a cloud provider.**

### When would you still choose something else?

Always corner cases:

| Requirement | Choose |
|---|---|
| Advanced security + BGP routing | **Calico** |
| High-performance networking + security | **Cilium** |
| Simple/lightweight, no NetworkPolicy needed | **Flannel** |
| Encrypted pod-to-pod traffic | **Weave Net** |

**On-premises:** you generally *cannot* use AWS VPC CNI or Azure CNI (unless you're prepared to tune and tweak) — so on-prem clusters use Calico, Cilium, Flannel, etc.

### The takeaway

> **Multiple options exist so that *you*, the consumer, choose CRI or CNI based on your requirement.** That is the point of the modular design.

---

## 8) CSI — Container Storage Interface

Placed here deliberately **before** the Kubernetes volumes lecture.

### Recap from Day 24 — Docker's two storage drivers

| Driver | Handles | Dies with container? |
|---|---|---|
| **Storage driver** | **Ephemeral** data — the writable layer | **Yes** |
| **Volume driver** | **Persistent** data — external disks | **No** |

### Kubernetes behaves the same way

- Create a pod, write data into its container, terminate the pod → **the data is gone**, because that container's **writable layer was ephemeral**.
- Want to retain data — logs, application data, **stateful applications** — → you attach a **persistent disk**, and that's the **volume driver** role.

> **Kubernetes' equivalent of Docker's volume driver is the CSI.**

### What CSI is

> **CSI = Container Storage Interface** — again a **set of rules/standards written by the Kubernetes community**.

Adhere to the standard, and your plugin can work with Kubernetes to **assign external storage to pods**.

### Why you need a CSI plugin

**To interact with external storage.** Without it, Kubernetes has no way to talk to a vendor's storage system.

### CSI drivers (examples)

| Environment | Driver |
|---|---|
| **AWS block storage** | **EBS CSI driver** |
| **AWS file storage** | **EFS CSI driver** |
| **GCP** | **Persistent Disk CSI driver** |
| **Azure** | Azure Disk / Files CSI drivers |
| **VMware ESXi** (now Broadcom) | vSphere CSI driver → connects pods to **VMFS** datastores |

So: on AWS → an **EBS** driver; need **EFS** → a different driver; on GCP → **PD** driver. Each vendor ships a driver that speaks the CSI standard.

### CSI responsibilities

| Responsibility | Meaning |
|---|---|
| **Volume lifecycle management** | Create / attach / detach / delete volumes |
| **Snapshot and cloning** | Point-in-time copies, clone a volume |
| **Expansion and resizing** | Grow a volume |
| **Dynamic volume provisioning** | **The big one** — see below |

### Dynamic volume provisioning (in plain English)

> A pod says **"I want 10 GB."** The CSI driver **creates** a 10 GB **EBS volume** (on AWS) **on demand** and **assigns it to the pod** — no human in the loop.

This is what makes storage *cloud-native*: no pre-creating disks by hand, no tickets to a storage team.

---

## 9) CRI vs CNI vs CSI — One Table

| | **CRI** | **CNI** | **CSI** |
|---|---|---|---|
| **Stands for** | Container **Runtime** Interface | Container **Network** Interface | Container **Storage** Interface |
| **Solves** | How containers are **created/run** | How pods **talk** to each other | How pods get **persistent storage** |
| **Kubernetes' stance** | "I don't create containers" | "I don't do pod networking" | "I don't do storage" |
| **Core examples** | containerd, CRI-O, Podman, Kata, gVisor | Calico, AWS VPC CNI, Azure CNI, Cilium, Flannel, Weave Net | AWS EBS/EFS, GCP PD, Azure Disk, vSphere |
| **Key responsibilities** | Lifecycle, images, logging, security | Pod networking, IPAM, routing, security enforcement | Volume lifecycle, snapshots, resizing, **dynamic provisioning** |
| **Docker equivalent** | Docker Engine / runc | Docker bridge networking | **Volume drivers** (`local`, AWS, Azure, GCP) |
| **Typical bug it causes** | Pods stuck in `ContainerCreating` | Pods can't reach each other / DNS breaks | PVC stuck `Pending` / volume won't mount |

---

## 10) Benefits of the Modular Architecture

| Benefit | Explanation |
|---|---|
| **1. Interoperability** | Use various plugins and third-party tooling **without disturbing the Kubernetes core** → much better interoperability |
| **2. Flexibility and vendor neutrality** | Multiple vendors for CNI, CRI, and CSI — **you choose what works best for you** |
| **3. Encourages innovation** | Each company/organization can build and enhance **its own** plugin. Kata Containers offers isolation CRI-O does not → a customer needing a highly secure runtime has an option |
| **4. Scalability and maintainability** | Individual components can be **scaled and upgraded independently**, improving reliability and maintainability |

> Benefit #4 is the deep one: because the core and the plugins ship and upgrade on **different cadences**, you can patch your CNI without touching Kubernetes, and upgrade Kubernetes without changing your storage driver.

---

## 11) Key Takeaways

1. **Kubernetes is modular by design** — the core does **container orchestration** and outsources everything else to **plugins, add-ons, and third-party integrations**, defined by **standards**.
2. **Decoupling is the course's recurring theme** — monolith → 3-tier → microservices, and Kubernetes itself is decoupled into core + plugins.
3. **Core = control plane + node components**: API Server (entry point), Scheduler (placement), Controller Manager (desired vs current state), **etcd** (database), Cloud Controller Manager (cloud resources).
4. **Node core = kubelet** (container creation + monitoring) **and kube-proxy** (Service↔Pod networking).
5. **The Kubernetes community owns the core** — developers, DevOps engineers, and organizations (Google, AWS, Red Hat, Ericsson).
6. **Not core:** plugins (**CRI/CNI/CSI**), add-ons (ingress, monitoring, service mesh), third-party extensions (**Helm**, Prometheus).
7. **CRI = standards for container runtimes.** Adhere and you can write your own. Plugins: **containerd** (default, lightweight), **CRI-O** (OpenShift), **Podman**, **Kata** (hardware isolation), **gVisor** (user-space sandbox).
8. **CRI is not core** because Kubernetes' job is orchestration, not container creation/security.
9. **CNI = standards for pod networking.** Plugins: **Calico** (security + BGP), **AWS VPC CNI**, **Azure CNI**, **Cilium** (performance), **Flannel** (lightweight, **no NetworkPolicy support**), **Weave Net** (encryption).
10. **Use the cloud-native CNI on a cloud provider** — features like **pod security groups** (AWS VPC CNI) plus vendor support aren't available elsewhere. But it's **not mandatory**; Calico/Cilium work fine.
11. **CSI = standards for persistent storage**, replacing Docker's volume drivers. Drivers: **AWS EBS/EFS**, **GCP PD**, **Azure Disk**, **vSphere**.
12. **CSI does dynamic provisioning** — ask for 10 GB, get a 10 GB EBS volume created and attached automatically.
13. **Docker mapping:** storage driver ≈ ephemeral (CRI-adjacent), **volume driver ≈ CSI**.
14. **Four benefits:** interoperability, flexibility + vendor neutrality, innovation, independent scalability/maintainability.

---

## 12) Commands to Verify Your Plugins

```bash
# Which container runtime (CRI) each node is using?
kubectl get nodes -o wide
kubectl describe node <node> | Select-String -Pattern "Container Runtime|Runtime Version"

# Which CNI is running? (look for calico / cilium / flannel / aws-node DaemonSets)
kubectl get pods -n kube-system
kubectl get daemonsets -n kube-system

# Which CSI drivers are installed?
kubectl get csidrivers
kubectl get storageclass

# Pod networking sanity check
kubectl run nginx --image=nginx
kubectl run test --image=busybox --rm -it -- wget -qO- nginx
```

> On `kind` (the course's test cluster) the CNI is **kindnet** by default, and the runtime is **containerd** — which is exactly why the Day 21/22 demos "just worked" without a separate CNI install.

---

## 13) Quick Self-Check

1. State Kubernetes' core purpose in one sentence. Name three things it deliberately does not handle.
2. Why is decoupling the same principle in microservices *and* in Kubernetes' architecture?
3. List the five control plane components and one job each.
4. What does kube-proxy do, and what does kubelet do?
5. Who maintains Kubernetes core, and why does that matter for feature delivery?
6. What are the three plugin categories, and give one example of each?
7. What does CRI standardise, and why is the runtime *not* part of core?
8. Which runtime is the default for most setups? Which one does OpenShift use?
9. Why does Kata Containers exist when containerd already works?
10. What does CNI standardise? Name four responsibilities.
11. Which CNI does **not** support NetworkPolicies?
12. You're on EKS. Must you use AWS VPC CNI? What do you gain/lose by choosing Calico instead?
13. What is the Kubernetes equivalent of Docker's volume drivers, and what does it let you do?
14. Explain dynamic volume provisioning with a 10 GB ask on AWS.
15. Give the four benefits of a modular architecture.
16. Which of CRI/CNI/CSI would be at fault if pods can't resolve DNS? If a PVC stays `Pending`?

---

## What's Next (Day 26)

- **Ephemeral storage** — `emptyDir` volumes (pod-scoped sharing between containers) and the **downwardAPI** (pod metadata as env vars or files).
- **Persistent storage** — PVs, PVCs, StorageClasses — follows on Day 27.

---

*End of Day 25 notes.*
