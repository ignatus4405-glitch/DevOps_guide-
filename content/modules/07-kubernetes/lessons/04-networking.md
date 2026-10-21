---
id: k8s-networking
title: Сеть Kubernetes: CNI, Service, Ingress
minutes: 32
---

# Сеть Kubernetes: CNI, Service, Ingress

![Путь запроса в Kubernetes](assets/img/kubernetes-networking.svg)

Сеть в Kubernetes — самая частая тема на собеседованиях и самая частая причина
«под работает, а трафик не идёт». Разберём три слоя: поды, сервисы, вход.

## Модель сети

Kubernetes требует:

1. Каждый под имеет уникальный IP.
2. Поды общаются друг с другом напрямую, без NAT.
3. Поды и ноды видят друг друга.

Реализует это **CNI-плагин**: Calico, Cilium, Flannel, Weave. Он настраивает
маршруты, overlay-сети или eBPF-программы.

```bash
kubectl get pods -n kube-system | grep -E 'calico|cilium|flannel'
kubectl get nodes -o wide
```

## Pod IP — не адрес для клиентов

IP пода меняется при пересоздании. Клиенты не должны обращаться к нему напрямую.

```bash
kubectl get pods -o wide
# app-7d9f-abc   10.244.1.15
kubectl delete pod app-7d9f-abc
kubectl get pods -o wide
# app-7d9f-def   10.244.2.7   <- другой IP
```

## Service: стабильный адрес

Service — виртуальный IP (ClusterIP) и правило балансировки на поды по selector.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
  type: ClusterIP
```

| Тип | Доступ | Когда |
| --- | --- | --- |
| ClusterIP | внутри кластера | по умолчанию |
| NodePort | IP ноды + порт 30000–32767 | отладка, on-prem |
| LoadBalancer | внешний LB облака | публичный сервис |
| ExternalName | CNAME на внешний сервис | интеграция с внешней БД |

Важно: `port` — порт сервиса, `targetPort` — порт контейнера. Путаница между ними
даёт «сервис есть, но connection refused».

Проверка:

```bash
kubectl get endpoints api
kubectl get endpointslices -l kubernetes.io/service-name=api
```

Пустой `ENDPOINTS` — selector не совпадает с метками подов или поды не Ready.
Это первое, что нужно смотреть.

## DNS внутри кластера

```
api.default.svc.cluster.local
```

Короткое имя `api` работает в том же namespace. Из другого — `api.default` или
полное FQDN.

```bash
kubectl run tmp --rm -it --image=busybox --restart=Never -- nslookup api
```

Частые проблемы:

- CoreDNS не запущен;
- NetworkPolicy блокирует UDP 53;
- `ndots:5` в resolv.conf пода — внешние имена пробуются как внутренние;
- под в другом namespace.

## Ingress: HTTP-маршрутизация

Ingress описывает правила «хост/путь → сервис». Реализует его ingress-controller
(nginx, Traefik, Envoy).

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  tls:
    - hosts: [api.example.com]
      secretName: api-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
```

Проверка:

```bash
kubectl get ingress
kubectl describe ingress api
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller
```

Ingress — не «балансировщик», а декларация. Без установленного контроллера он
ничего не делает.

## NetworkPolicy: ограничение трафика

По умолчанию все поды видят всех. NetworkPolicy включает изоляцию:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-allow
spec:
  podSelector:
    matchLabels: { app: api }
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels: { app: frontend }
      ports:
        - port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels: { app: db }
      ports:
        - port: 5432
```

Требуется CNI с поддержкой policy (Calico, Cilium). Flannel сам по себе — нет.

## Отладка сети

```bash
kubectl run tmp --rm -it --image=nicolaka/netshoot -- bash
# внутри:
nslookup api
curl -v http://api
tcpdump -i any port 8080
```

`netshoot` содержит dig, curl, tcpdump, mtr — незаменим для разбора.

## Подробный разбор темы

Pod получает собственный IP в модели CNI, и Pod-to-Pod связь обычно возможна между узлами без NAT внутри кластера. Service создаёт стабильное имя и виртуальный IP над меняющимися Pod endpoints. Ingress или Gateway добавляет входную HTTP-маршрутизацию; это отдельный компонент и отдельные правила TLS.

Если соединение не работает, сравните DNS изнутри Pod, endpoints Service, NetworkPolicy, CNI и внешний ingress. `kubectl get endpoints` помогает заметить, что Service не выбрал ни одного готового Pod; `kubectl exec` проверяет путь из правильного namespace, но использовать его следует с учётом прав. Внимательно относитесь к `localhost`: внутри Pod он указывает на конкретный сетевой namespace, не на Service или другой Pod.

## Проверьте себя

1. Почему нельзя обращаться к поду по IP?
2. Что означает пустой список endpoints у Service?
3. Чем port отличается от targetPort?
4. Зачем нужен ingress-controller, если есть Ingress?

!!! tip "Практика"
    Задача «Сервис и Ingress» в практикуме: пройти путь от пода до внешнего
    запроса и найти разрыв, если он есть.
