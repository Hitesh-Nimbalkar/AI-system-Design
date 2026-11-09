# mTLS in Kubernetes & the kubeconfig File — Part 2 (Day 32)

> Source: Day 32 of a Certified Kubernetes Administrator (CKA) 2025 course — **part 2 of the 4-part TLS masterclass**.
> Topic: What **mutual TLS** is, why **every** Kubernetes cluster runs it, and how **`~/.kube/config`** + **contexts** carry your identity to the right cluster without you ever typing a certificate.
> Prerequisite: Day 30 (symmetric/asymmetric), Day 31 (client/server roles, one-way TLS, CAs, `openssl`).
> Next: part 3 — Kubernetes' **internal certificates and private CAs**.

---

## 1) What Is Mutual TLS?

> **mTLS is an extension of standard TLS where both the client and the server authenticate each other using digital certificates.**

One-way TLS: the **server** proves who it is; the client is anonymous.
mTLS: **both** prove who they are.

### The flow, hop by hop

```
Seema ──(1)──► API server ──(2)──► etcd
       kubectl
```

**Hop (1) — Seema → API server**

| Step | Who acts |
|---|---|
| 1 | Seema initiates `kubectl get pods` |
| 2 | **API server proves its identity** (presents its certificate) |
| 3 | Seema verifies it, using the **Kubernetes CA certificate** |
| 4 | **Seema proves her identity** (presents her client certificate) |
| 5 | API server verifies it — and only then proceeds |

**Hop (2) — API server → etcd**

The pod list isn't *in* the API server; it must fetch it from etcd. And the same dance repeats **in the other direction**:

| Step | Who acts |
|---|---|
| 1 | API server is now the **client** (it initiated) |
| 2 | **etcd proves its identity** |
| 3 | **API server proves its identity** |
| 4 | etcd returns the data |

> **Two hops, two independent mTLS handshakes.** Each side proves itself on every connection, in both roles.

### The ordering rule, again

> It is **always the server that proves its identity first** — in mTLS and in SSH.

**Why?** So a client never sends sensitive information (a certificate, a token, a password) to a server that hasn't proven itself.

```
Server proves ──► Client verifies ──► Client proves ──► Server verifies ──► Connection proceeds
```

> Note where the API server's dual role (Day 31) lives: its **serving certificate** (for kubectl connections) and its **client certificate** (for etcd connections) both sit on the control-plane node — typically under `/etc/kubernetes/pki/` — **not** in your kubeconfig. Your kubeconfig only ever holds **your** credentials. Part 3 opens up that directory.

---

## 2) One-Way TLS vs mTLS

| | **One-way TLS** | **mTLS** |
|---|---|---|
| **Authentication** | **Server only** | **Both directions** |
| **Identity verification** | Server proves | **Server *and* client prove** |
| **Certificates required** | **Server certificate only** | **Server + client certificates** |
| **Ordering** | Server first | **Server first**, then client |
| **Security level** | Strong | **Stronger** |
| **Use cases** | **Public websites** (pinkbank.com, GitHub) | **Microservices, Kubernetes**, service meshes |

### Why isn't public TLS mutual?

When Seema visits pinkbank.com, only pinkbank presents a certificate — **Seema presents nothing**. It would be absurd to demand a client certificate from every anonymous visitor to a public site.

But in a cluster, **every participant is known in advance** — so mutual proof is both possible and expected.

---

## 3) Kubernetes Runs on mTLS — Everywhere

> **All production implementations use mTLS.**

| Cluster type | mTLS? |
|---|---|
| **Managed** — EKS, AKS, GKE | ✅ |
| **OpenShift** | ✅ |
| **kind** | ✅ |
| **kubeadm** | ✅ |

### "But we never supplied a certificate!"

The obvious objection — and the one this whole lecture answers:

> *"We've been typing commands since the start of the course. We never specified **which** API server to connect to (there are millions of API servers in the world), and we never provided a certificate. So how is this working?"*

**Answer: the Kubernetes configuration file.**

> You *can* configure a cluster to use one-way TLS. **It is not recommended at all.**

> The kubeconfig is doing three jobs silently: **which** cluster, **which** identity, and **which** namespace.

---

## 4) The kubeconfig File — Three Sections

> **Path:** `~/.kube/config` — the file is literally named **`config`**, inside the `.kube` directory in your home directory.
> **Full name:** the **Kubernetes configuration file**. It holds **how to connect to the cluster** and **what authentication information to use**.

### The problem it solves

As a DevOps engineer you don't manage one cluster — you manage **five, six, many**. In the morning you work on **dev**; in the afternoon, **production**.

> How do you ensure commands go to the **right cluster** at the right time?

That's what **kubeconfig + contexts** do.

### The three sections

```
~/.kube/config
├── clusters   []   → WHERE to connect  (API server + CA certificate)
├── users      []   → WHO you are       (client certificate + private key)
└── contexts   []   → WHICH pair+ns     (user + cluster + namespace)
```

> **All three are plurals, and all three are lists.** You can hold many entries of each — which is exactly how one file serves many clusters.

### One-liners (memorise these)

| Section | Question it answers |
|---|---|
| **User** | *Who is accessing the cluster?* |
| **Cluster** | *Which Kubernetes cluster?* |
| **Context** | *How does a user access a specific cluster* — plus **optionally a namespace** |

### The user-naming nuance

"Seema is a Kubernetes user" is too simple. Seema's **identity can differ per cluster**:

| Cluster | Seema's user entry |
|---|---|
| dev | `seema-dev-user` |
| staging | `seema-staging-user` |
| prod | `seema-prod-user` |

Same human, **three different certificates** — because trust isn't transferable across clusters.

### The context nuance

> **A context marries a user to a cluster** (and can pin a namespace).

```
seema@dev-cluster   →  user: seema  +  cluster: dev-cluster   +  ns: app1-dev-ns
seema@prod-cluster  →  user: seema  +  cluster: prod-cluster  +  ns: app1-prod-ns
```

Switch to `seema@dev-cluster` → commands go to **dev**. Switch to `seema@prod-cluster` → commands go to **production**.

And within one context, the namespace is a **setting you can change** without switching contexts:

```
seema@dev-cluster, ns app1   →  run in app1
seema@dev-cluster, ns app2   →  same context, different namespace
```

---

## 5) Anatomy of the File

```yaml
apiVersion: v1
kind: Config
current-context: seema@dev-cluster
preferences: {}

clusters:
  - name: dev-cluster
    cluster:
      server: https://1.2.3.4:6443
      certificate-authority-data: <base64 of the K8s CA cert>

  - name: staging-cluster
    cluster: { server: ..., certificate-authority-data: ... }

  - name: prod-cluster
    cluster: { server: ..., certificate-authority-data: ... }

users:
  - name: seema
    user:
      client-certificate-data: <base64 of Seema's client cert>
      client-key-data:         <base64 of Seema's private key>

contexts:
  - name: seema@dev-cluster
    context:
      cluster: dev-cluster
      user: seema
      namespace: app1-dev-ns

  - name: seema@staging-cluster
    context: { cluster: staging-cluster, user: seema, namespace: app1-staging-ns }

  - name: seema@prod-cluster
    context: { cluster: prod-cluster, user: seema, namespace: app1-prod-ns }
```

### Field by field

| Field | What it holds | Why it's needed |
|---|---|---|
| **`clusters[].cluster.server`** | The API server's **address + port** | *This* is how kubectl knows **where** to connect — it's the entry point to the cluster |
| **`clusters[].cluster.certificate-authority-data`** | **base64 of the Kubernetes CA certificate** | So the client can **verify the API server's certificate** |
| **`users[].user.client-certificate-data`** | **base64 of the client certificate** | This is **how Seema presents her identity** |
| **`users[].user.client-key-data`** | **base64 of the private key** | Proves the certificate is hers. **Never leaves the machine** |
| **`contexts[].context.{cluster,user,namespace}`** | The pairing | Ties identity to destination |
| **`current-context`** | Which context is active | What `kubectl` uses by default |

### Why `certificate-authority-data` is the crux

Recall Day 31: to verify that a server's certificate was signed by a CA, **you need that CA's certificate**.

> *"But where is this certificate? I don't have it."*

**It's embedded in the kubeconfig.** So when the API server presents its certificate, kubectl can verify it **locally, offline** — no network call, no manual step.

That's the whole trick: **the trust anchor ships with the client.**

### Why the client key is safe there

- The **private key never leaves** the machine — it's used locally to sign the handshake.
- `client-key-data` is the key **at rest** on disk, protected by file permissions — not transmitted.

> **A kubeconfig is a credential file.** Treat it exactly like an SSH private key (Day 31's git warning applies verbatim).

### And the encoding caveat

> **Everything certificate-related in a kubeconfig is base64-encoded — and encoding is not encryption.**

Anyone who reads your kubeconfig can decode both the certificate **and the private key**. File permissions and RBAC are the real protection, not the base64. (Same lesson as Secrets in Day 28.)

---

## 6) Demo — Working with kubeconfig and Contexts

### Rule zero: use `kubectl config`, don't hand-edit

> **Never edit `~/.kube/config` manually.** If you must, **take a backup first.**

```bash
cp ~/.kube/config ~/.kube/config.bak
```

Every operation below has a CLI command — and the CLI won't corrupt your indentation.

```bash
kubectl config -h        # the full subcommand list
```

| Subcommand | Purpose |
|---|---|
| `view` | Display the merged config |
| `get-contexts` | List contexts (`*` marks the active one) |
| `use-context` | Switch the active context |
| `set-context` | Create/modify a context (incl. `--current --namespace`) |
| `current-context` | Print just the active context |
| `delete-context` / `delete-cluster` / `delete-user` | Remove entries |
| `set-cluster` / `set-credentials` | Add cluster/user (part 4) |

### Step 1 — Look at what you have

```bash
kubectl config view
```

On a fresh **kind** cluster you'll see **one entry in each section** — cluster, context, user — all named the same thing.

```yaml
clusters:
  - name: kind-my-second-cluster
    cluster:
      certificate-authority-data: <base64>
      server: https://127.0.0.1:xxxxx

users:
  - name: kind-my-second-cluster
    user:
      client-certificate-data: <base64>
      client-key-data: <base64>

contexts:
  - name: kind-my-second-cluster
    context:
      cluster: kind-my-second-cluster
      user: kind-my-second-cluster
      namespace: default
```

> **Note the kind naming collision:** kind names the **cluster, context, and user identically** (`kind-<name>`). That's confusing, and it's why the real-world example in Section 5 uses distinct names (`seema`, `dev-cluster`, `seema@dev-cluster`).

### Step 2 — Create a second cluster (and watch the file change)

```bash
kind create cluster --name test
kind get clusters
# kind-my-second-cluster
# test
```

```bash
kubectl config view
```

**Now every section is a list with two entries:**

| Section | Entries |
|---|---|
| `clusters` | `kind-my-second-cluster`, **`kind-test`** |
| `contexts` | `kind-my-second-cluster`, **`kind-test`** |
| `users` | `kind-my-second-cluster`, **`kind-test`** |

> **Creating a cluster mutated the shared config automatically** — kind writes the new cluster/user/context into `~/.kube/config` and makes it current.

### Step 3 — Which context am I in?

```bash
kubectl config get-contexts
```

```
CURRENT   NAME                      CLUSTER                   AUTHINFO                  NAMESPACE
*         kind-test                 kind-test                 kind-test                 default
          kind-my-second-cluster    kind-my-second-cluster    kind-my-second-cluster    default
```

The **asterisk** is the active context. `kubectl get nodes` now goes to **kind-test**:

```bash
kubectl get nodes
# a single control-plane node — kind's default layout
```

> **This is the whole point of contexts:** the command didn't change, only the context did — and it went to a completely different cluster.

### Step 4 — Switch context

```bash
kubectl config use-context kind-my-second-cluster
# Switched to context "kind-my-second-cluster".

kubectl config get-contexts      # asterisk moved
kubectl get nodes                # now 3 nodes (control plane + 2 workers)
```

### Step 5 — Change the namespace *within* a context

```bash
kubectl config set-context --current --namespace=app1-ns
# Context "kind-my-second-cluster" modified.

kubectl config get-contexts      # NAMESPACE column now shows app1-ns
kubectl get pods
# No resources found in app1-ns namespace.
```

Then, when the work moves:

```bash
kubectl config set-context --current --namespace=app2-ns
```

> **Same cluster, same identity — different namespace.** You never retype `-n`. This is the mechanism from Day 29's demo (and its gotcha: the context keeps pointing at a namespace even after you delete it).

### Step 6 — Delete entries from the config

```bash
kubectl config delete-context kind-test
kubectl config delete-cluster kind-test
kubectl config delete-user   kind-test

kubectl config view      # back to a single cluster
```

> Note the **order independence**: you're just removing three list entries. (In real life, `kind delete cluster --name test` removes them for you — but knowing the manual commands matters, because other tools don't always clean up.)

### Step 7 — Delete the cluster itself

```bash
kind delete cluster --name test
```

> Deleting a kind cluster **also removes its entries** from `~/.kube/config`.

---

## 7) Multiple kubeconfig Files

You don't have to keep everything in one file. `kubectl` supports several via:

```bash
# one file
kubectl --kubeconfig /path/to/config get pods

# many files, merged in order (first match wins)
export KUBECONFIG=~/.kube/config:~/.kube/dev-config:~/.kube/prod-config
kubectl config view            # shows the MERGED result
```

| Mechanism | Notes |
|---|---|
| `--kubeconfig` flag | Per-command override |
| `KUBECONFIG` env var | Colon-separated list on Linux/macOS (`;` on Windows) |
| Merging | Duplicate names: **first file wins** |

> The instructor points you to the GitHub notes for the full treatment rather than demoing it — but `KUBECONFIG` is the standard way teams keep **per-environment credentials** from contaminating a single file.

---

## 8) Security Notes (the ones that get people fired)

| Rule | Why |
|---|---|
| **`chmod 600 ~/.kube/config`** | It contains a **private key** |
| **Never commit it to git** | Same as leaking an SSH key — history is forever |
| **Back it up before editing** | A corrupt kubeconfig locks you out of every cluster |
| **Prefer `kubectl config`** | Hand-editing YAML breaks indentation and merging |
| **Base64 ≠ encryption** | Anyone with the file can decode the key |
| **A context is not a security boundary** | It's a *convenience*. Real authorization is **RBAC** — a user can still be blocked (or allowed) per namespace regardless of context |
| **`use-context` is not a safety switch** | Being "in dev" doesn't prevent a typo'd `kubectl delete` from hitting prod if the context changed |

> The last two matter: **contexts tell kubectl where to send commands; RBAC decides what is allowed.** Confusing the two is how people assume they're safe when they aren't.

---

## 9) Key Takeaways

1. **mTLS = both client and server authenticate with digital certificates.** One-way TLS authenticates the server only.
2. **Kubernetes runs on mTLS in every hop** — kubectl→API server, API server→etcd — and **each hop is independent**.
3. **The API server is both server and client**, so it holds both a serving certificate and a client certificate.
4. **The server always proves first**, then the client — so clients never hand credentials to unverified servers.
5. **All production clusters use mTLS** — EKS, AKS, GKE, OpenShift, kubeadm, kind. One-way TLS is configurable and **not recommended**.
6. **kubeconfig exists because we never type a server address or a certificate** — it supplies both, silently.
7. **`~/.kube/config`** has three list sections: **clusters** (where), **users** (who), **contexts** (which pair + namespace).
8. **`server`** = API server address; **`certificate-authority-data`** = the CA cert used to **verify the API server**.
9. **`client-certificate-data`** = your identity; **`client-key-data`** = the private key that proves it — and it **never leaves the machine**.
10. **A context marries a user to a cluster**, optionally with a **namespace**.
11. **One human can have different user entries per cluster** — identities don't transfer across clusters.
12. **Switch clusters with `use-context`; switch namespaces with `set-context --current --namespace`** — no `-n` on every command.
13. **Everything certificate-related in kubeconfig is base64** — encoding, **not** encryption.
14. **Never hand-edit; always back up.** `kubectl config` is the safe interface.
15. **`KUBECONFIG` / `--kubeconfig`** let you split credentials across files and merge them.
16. **Contexts are convenience, not security.** **RBAC** is the enforcement layer.
17. **Creating/deleting a kind cluster edits your kubeconfig automatically** — and kind names the cluster, context, and user identically, which is confusing.

---

## 10) Essential Commands

```bash
# --- Inspect ---
kubectl config view                       # whole effective config
kubectl config view --minify              # only the current context's bits
kubectl config current-context            # just the active context name
kubectl config get-contexts               # list, * marks active
kubectl config get-clusters
kubectl config get-users

# --- Switch ---
kubectl config use-context <context>
kubectl config set-context --current --namespace=<ns>   # fastest namespace switch

# --- Create/modify (part 4 preview) ---
kubectl config set-cluster <name> --server=https://... --certificate-authority=ca.crt
kubectl config set-credentials <name> --client-certificate=client.crt --client-key=client.key
kubectl config set-context <name> --cluster=<c> --user=<u> --namespace=<ns>
kubectl config rename-context <old> <new>

# --- Remove ---
kubectl config delete-context <name>
kubectl config delete-cluster <name>
kubectl config delete-user    <name>

# --- Multiple files ---
kubectl --kubeconfig /path/to/config get pods
export KUBECONFIG=~/.kube/config:~/.kube/prod-config

# --- kind ---
kind create cluster --name test
kind get clusters
kind delete cluster --name test

# --- Hygiene ---
cp ~/.kube/config ~/.kube/config.bak && chmod 600 ~/.kube/config
```

---

## 11) Quick Self-Check

1. Define mTLS in one sentence. What does one-way TLS skip?
2. In `kubectl get pods`, who authenticates whom, and in what order?
3. Why does the order matter — what is being protected?
4. Which certificate does the API server use when talking to etcd, and why is that surprising?
5. Does Kubernetes *have* to use mTLS, or is one-way TLS possible? What's the recommendation?
6. Name the three sections of a kubeconfig and the question each answers.
7. Which field tells kubectl **where** to connect?
8. Which field lets kubectl **verify** the API server, and where does that certificate come from?
9. Which two fields present the client's identity, and which one must never leave the machine?
10. What exactly does a context marry together?
11. Can one person have different user entries for different clusters? Why would they?
12. Which commands switch a cluster vs switch a namespace?
13. Why does the browser-free kubectl not need to contact the CA during a handshake?
14. Is the private key in a kubeconfig encrypted? What is the real protection?
15. Why is "I'm in the dev context" not a safety guarantee?
16. What does `KUBECONFIG` do with multiple files, and who wins on a name clash?
17. Why does a kind-created cluster appear identically named in all three sections?

---

## What's Next (Day 33 — Part 3)

- **Kubernetes internal certificates and private CAs** — how the cluster's own CA issues certificates to components, where they live on disk, and how cluster communication is secured.

---

*End of Day 32 notes.*
