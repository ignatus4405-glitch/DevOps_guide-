---
id: ansible
title: Ansible: конфигурация серверов без агентов
minutes: 40
---

# Ansible: конфигурация серверов без агентов

**Ansible подключается по SSH и приводит сервер к описанному состоянию.**
Плейбуки идемпотентны: повторный запуск не «сломает» систему, а подтвердит
соответствие. Агентов устанавливать не нужно — только Python и SSH на целевом хосте.

## Инвентарь и первый плейбук

```ini
# inventory/prod.ini
[web]
web1.example.com
web2.example.com

[db]
db1.example.com

[all:vars]
ansible_user=deploy
ansible_ssh_private_key_file=~/.ssh/id_lab
ansible_python_interpreter=/usr/bin/python3
```

```yaml
# playbook-web.yml
---
- name: Настроить веб-серверы
  hosts: web
  become: true                    # sudo
  vars:
    app_port: 8080
    nginx_worker_processes: auto
  tasks:
    - name: Установить пакеты
      ansible.builtin.apt:
        name: [nginx, curl, ca-certificates]
        state: present
        update_cache: true
        cache_valid_time: 3600

    - name: Положить конфиг nginx
      ansible.builtin.template:
        src: templates/app.conf.j2
        dest: /etc/nginx/conf.d/app.conf
        owner: root
        group: root
        mode: "0644"
        validate: "nginx -t -c %s"      # проверка ДО применения
      notify: reload nginx               # обработчик сработает только при изменении

    - name: Убедиться, что сервис запущен и включён
      ansible.builtin.systemd:
        name: nginx
        state: started
        enabled: true

    - name: Создать пользователя приложения
      ansible.builtin.user:
        name: appsvc
        system: true
        shell: /usr/sbin/nologin
        create_home: false

  handlers:
    - name: reload nginx
      ansible.builtin.systemd: { name: nginx, state: reloaded }
```

```bash
ansible-playbook -i inventory/prod.ini playbook-web.yml --check --diff   # «примерка»
ansible-playbook -i inventory/prod.ini playbook-web.yml
ansible web -i inventory/prod.ini -m ansible.builtin.setup | head -30    # факты о хостах
```

| Модуль | Зачем |
| --- | --- |
| `apt`/`dnf` | пакеты |
| `template`/`copy` | файлы и конфиги |
| `systemd` | сервисы |
| `user`/`group` | пользователи |
| `lineinfile`/`blockinfile` | точечные правки конфигов |
| `ufw`/`firewalld` | правила файрвола |
| `docker_container` | запуск контейнеров |

## Роли: структура для повторного использования

```text
roles/nginx/
├── defaults/main.yml      # значения по умолчанию (низший приоритет)
├── vars/main.yml          # «жёсткие» переменные роли
├── tasks/main.yml         # список задач
├── handlers/main.yml      # обработчики (reload/restart)
├── templates/
│   └── app.conf.j2
├── files/
└── meta/main.yml          # зависимости от других ролей
```

```yaml
- hosts: web
  become: true
  roles:
    - role: nginx
      vars: { app_port: 8080 }
    - role: monitoring_agent
```

Шаблон Jinja2 для конфигурации:

```jinja
# templates/app.conf.j2
upstream app_backend {
{% for host in groups['app'] %}
    server {{ host }}:{{ app_port }} max_fails=3 fail_timeout=10s;
{% endfor %}
}
server {
    listen 80;
    server_name {{ ansible_fqdn }};
    location / { proxy_pass http://app_backend; }
}
```

## Vault: секреты в плейбуках

```bash
ansible-vault create group_vars/prod/vault.yml       # интерактивное создание
ansible-vault edit group_vars/prod/vault.yml
ansible-vault encrypt_string 'super-secret' --name 'db_password'
ansible-playbook playbook.yml --ask-vault-pass
ansible-playbook playbook.yml --vault-password-file ~/.vault_pass   # для CI — из секретов
```

```yaml
# group_vars/prod/vars.yml (без секретов, можно в Git)
db_host: db1.example.com
db_user: app
# значение db_password лежит в vault.yml и подставится автоматически
```

!!! warning "Важно"
    Пароль vault в CI храните в секретах CI (не в репозитории) и не передавайте в
    логи. Регулярно меняйте его: смена пароля = перешифровка всех vault-файлов.

## Идемпотентность и проверка результата

```bash
ansible-playbook site.yml --check --diff     # что изменится
ansible-playbook site.yml                    # применять
ansible all -i inventory/prod.ini -m ansible.builtin.command -a 'uptime'   # разовая команда
ansible-playbook site.yml --limit web1       # только один хост
ansible-playbook site.yml --start-at-task 'Положить конфиг nginx'
```

Признак правильного плейбука: **второй прогон показывает 0 changed**. Если задачи
постоянно «changed», где-то используется `command`/`shell` вместо идемпотентного
модуля или шаблон содержит переменную, меняющуюся каждый раз (например, дату).

## Terraform + Ansible: разделение ответственности

| Инструмент | Что делает | Не должен делать |
| --- | --- | --- |
| Terraform | создаёт ресурсы: сети, ВМ, БД, балансировщики | настраивать ПО внутри сервера |
| Ansible | настраивает ПО, конфиги, сервисы, пользователей | создавать облачные ресурсы |

Типовой конвейер: Terraform создаёт ВМ и пишет их адреса в inventory (через
`local_file` или dynamic inventory), затем Ansible настраивает. Всё — из Git, через
пайплайн с ревью.

## Короткое резюме

- Ansible работает по SSH без агентов, плейбуки идемпотентны.
- Роли структурируют конфигурацию; handlers перезапускают сервисы только при изменениях.
- `--check --diff` — безопасная проверка перед применением.
- Секреты — в Ansible Vault или внешнем хранилище; пароль не хранится в репозитории.

## Проверьте себя

1. Как понять, что плейбук действительно идемпотентен?
2. Зачем в модуле `template` параметр `validate`?
3. Где заканчивается ответственность Terraform и начинается ответственность Ansible?
