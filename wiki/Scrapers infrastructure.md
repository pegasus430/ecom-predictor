### **New scrapers infrastructure based on kubernetes. So we need to install and configure kubectl** 

----------

### Kube credentials:

[kube dashboard](https://ca-kube1.contentanalyticsinc.com/api/v1/proxy/namespaces/kube-system/services/kubernetes-dashboard/#!/job?namespace=scraper)

login: `admin`

pass: `ObFdKpWTmLM8MHfu/6tUiIwXuiXbwWtHtA+YMAdtRis=`

namespace: `scraper`

### Docker registry credentials:

[registry dashboard](https://nexus3.contentanalyticsinc.com/#browse/welcome)

login: `admin`

pass: `mewWUc`

----------

## Install kubectl
#### Download the latest release with the command:
```
curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl

```
#### Make the kubectl binary executable.
```
chmod +x ./kubectl
```
#### Move the binary in to your PATH.

```

sudo mv ./kubectl /usr/local/bin/kubectl

```
---
## Configure kubectl
#### In order for kubectl to find and access a Kubernetes cluster, it needs a kubeconfig file (`~/.kube/config`). Next step is to create kubeconfig file with content: 


```
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUM2RENDQWRDZ0F3SUJBZ0lCQURBTkJna3Foa2lHOXcwQkFRc0ZBREFsTVJFd0R3WURWUVFLRXdocmRXSmwKTFdGM2N6RVFNQTRHQTFVRUF4TUhhM1ZpWlMxallUQWVGdzB4TnpBM01Ua3hPREl5TURGYUZ3MHlOekEzTVRjeApPREl5TURGYU1DVXhFVEFQQmdOVkJBb1RDR3QxWW1VdFlYZHpNUkF3RGdZRFZRUURFd2RyZFdKbExXTmhNSUlCCklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUFzbXN0TDV6T1diNHpIbWp0V2NIeWFGWmgKVTdzdUl4QjUyVkVrT3NldWFsUkJTZHlPK0R2eEJJS1YwMVRZRWJhbFZSWmd2VGdUbThoQkRYZ1RONTIwYmFxVQpnTVNjRWtjUVN4dC9UR09HSGtpMGVnREIyV1QrSFFHeEhncDk4eWRHbW9jMUp5bmFiUm5YeXdoU1F2Q0Vqd1dpCnQ2V1lMd0xJZ2dCaEZqQm02bjNYc2t0cUpHR2xOVDloTTdTdXd0aTRjNGV1TVJ3ckpJZlZneGhOYTNiN3QzMFMKcjNQMUFrU1VRQ0dqTnowTkZ3ODZVQ05OcUk2ZkNaUmNDQk5lcUpWZkN5dk0zNENzYVVFMUtJTXljUUE3SVhLaQo3V3VVOGpyU0hTWU5NWkFFYTRoOUIwc1pINC9jWUZQR3BsMnp1bG1BMmo4SVM0bVVXcVdmSTF6WnZJZDRRUUlECkFRQUJveU13SVRBT0JnTlZIUThCQWY4RUJBTUNBcVF3RHdZRFZSMFRBUUgvQkFVd0F3RUIvekFOQmdrcWhraUcKOXcwQkFRc0ZBQU9DQVFFQWpvUEk3TUdINGFTNCtxZUYyZnBtZlEyOGZxeXVwR3NiOW5EWjJuNWQvVXpaWmZ3RwpaemxRSW5jOUNzMWlTS0FXL2p5aWttWGNWalJBL1FFQ1dsTHRMQXpaRUV3bmUwcUxFbTZ0NkxSbmNQZ2RsSExnCkJSRkh4ZVAxckhMS0VGVVRRb1VVRmtsQkpuM0pBdjRURlpnKzRLYjdJVE5HOEF1dytYMFl2QXJpb0hGVzRXa1AKOWVJZk5ma2kxTElGdURBT2lhY1g2MkNIVVZkWXBERkRKTWlZUXQ5K1BpeHRIRysvSTBYbG9tVnJjTlN1aHVLTgpmOXpEQkJnOWd2SlFiVkRQQ1d5dDh1Tm5JRk00MlVHZDVaMGNnOUVkcXdnRW5ZYzBVK0N4QXBVRVo0dVJPa2dpClpqcVlYTUljbE5nN0JBakRqb2FDbStRcGJGVkRPbUFraXRFcU9RPT0KLS0tLS1FTkQgQ0VSVElGSUNBVEUtLS0tLQ==
    server: https://ca-kube1.contentanalyticsinc.com
  name: kube-aws-ca-kube1-cluster
contexts:
- context:
    cluster: kube-aws-ca-kube1-cluster
    namespace: default
    user: kube-aws-ca-kube1-admin
  name: kube-aws-ca-kube1-context
current-context: kube-aws-ca-kube1-context
kind: Config
preferences: {}
users:
- name: kube-aws-ca-kube1-admin
  user:
    password: ObFdKpWTmLM8MHfu/6tUiIwXuiXbwWtHtA+YMAdtRis=
    username: admin
```

#### Next check that kubectl is properly configured by getting the cluster state:
```
kubectl cluster-info
```
#### Output:
```
Kubernetes master is running at https://ca-kube1.contentanalyticsinc.com
Heapster is running at https://ca-kube1.contentanalyticsinc.com/api/v1/proxy/namespaces/kube-system/services/heapster
KubeDNS is running at https://ca-kube1.contentanalyticsinc.com/api/v1/proxy/namespaces/kube-system/services/kube-dns
kubernetes-dashboard is running at https://ca-kube1.contentanalyticsinc.com/api/v1/proxy/namespaces/kube-system/services/kubernetes-dashboard

```


Building procedure
-------------

#### Cloning the watcher repo
```
git clone git@github.com:ContentAnalytics/scrapers_infrastructure.git
cd scrapers_infrastructure/
```
#### Building the docker image
Login to the docker registry
```
docker login -u admin -p mewWUc nexus3-registry.contentanalyticsinc.com
```
Next we need to get all tags for watcher image (`ca-watcher`)
```
curl -u admin:mewWUc https://nexus3-registry.contentanalyticsinc.com/v2/ca-watcher/tags/list

```
Output:
```
{
  "name": "ca-watcher",
  "tags": [
    "0.1"
  ]
}
```
So next tag is `0.2`. Building the image with tag `0.2` from current directory
```
docker build -t nexus3-registry.contentanalyticsinc.com/ca-watcher:0.2 .
```
Pushing new image to the docker repo
```
docker push nexus3-registry.contentanalyticsinc.com/ca-watcher:0.2
```
Building phase is finished.

Deploying procedure
-------------
#### Specify new image tag in the kube watcher config
Open and edit watcher config
```
kubectl -n watcher edit statefulset/watcher
```
Output:
```
...
      containers:
      - image: nexus3-registry.contentanalyticsinc.com/ca-watcher:0.1
        imagePullPolicy: Always
        name: watcher
        resources: {}
        terminationMessagePath: /dev/termination-log
        terminationMessagePolicy: File

...
```

Here we need to change the line:
```image: nexus3-registry.contentanalyticsinc.com/ca-watcher:0.1``` 

New line:
```image: nexus3-registry.contentanalyticsinc.com/ca-watcher:0.2```

Save and exit from editor. New config will be applied after the exiting from editor.

#### Deploy new watcher image

Firstly we need to delete current watcher. Getting running watcher:
```
kubectl -n watcher get pods

NAME        READY     STATUS    RESTARTS   AGE
watcher-0   1/1       Running   0          45s

```
Deleting the watcher:
```
kubectl -n watcher delete po watcher-0
```
After the watching deleted the new one will be deployed automatically.

Checking the watcher state:
```
kubectl -n watcher get pods

NAME        READY     STATUS    RESTARTS   AGE
watcher-0   1/1       Running   0          45s

```
Deploying phase is finished


Debagging
---------

Watcher logs:
```
kubectl -n watcher logs -f watcher-0 -c watcher
```

Deleting the watcher:
```
kubectl -n watcher delete po watcher-0
```

Stopping the watcher:
```
kubectl -n watcher delete statefulset watcher
```

Creating the watcher:
```
kubectl -n watcher apply -f watcher/templates/ca_watcher.yml
```

Watcher state:
```
kubectl -n watcher get pods

NAME        READY     STATUS    RESTARTS   AGE
watcher-0   1/1       Running   0          34s

```
```
kubectl -n watcher get statefulset

NAME      DESIRED   CURRENT   AGE
watcher   1         1         1m

```

Watcher details:
```
kubectl -n watcher describe pod watcher
```