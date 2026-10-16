#!/usr/bin/env python3
"""Генератор SVG-иллюстраций для курса.

Иллюстрации лежат в репозитории как готовые .svg (лёгкие, векторные, без
внешних зависимостей), но создаются этим скриптом — так их легко править и
дополнять. Запуск:  python tools/make_diagrams.py [--out content/assets/img]
"""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

FONT = "'Segoe UI','Inter','Noto Sans',sans-serif"
MONO = "'Cascadia Mono','Consolas',monospace"

PALETTE = {
    "blue": ("#1d3557", "#4f9cf9"),
    "green": ("#12402f", "#3ecf8e"),
    "orange": ("#4a2f12", "#f0b429"),
    "red": ("#4a1f1f", "#f2635f"),
    "purple": ("#2c2148", "#b18cff"),
    "grey": ("#222c3d", "#8fa3bf"),
}


class Svg:
    """Мини-конструктор SVG с сеткой 24px и пресетами фигур."""

    def __init__(self, width: int, height: int, title: str) -> None:
        self.width = width
        self.height = height
        self.parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
            f'<rect width="{width}" height="{height}" rx="14" fill="#0f172a"/>',
            f"<title>{escape(title)}</title>",
            "<defs>"
            '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
            'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3bf"/></marker>'
            "</defs>",
        ]

    def box(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        lines: list[str] | None = None,
        color: str = "blue",
        mono: bool = False,
    ) -> Svg:
        bg, border = PALETTE[color]
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{bg}" stroke="{border}" stroke-width="1.5"/>'
        )
        self.parts.append(
            f'<text x="{x + w / 2}" y="{y + 26}" text-anchor="middle" font-family="{FONT}" '
            f'font-size="15" font-weight="700" fill="#e6edf7">{escape(title)}</text>'
        )
        for index, line in enumerate(lines or []):
            family = MONO if mono else FONT
            self.parts.append(
                f'<text x="{x + w / 2}" y="{y + 46 + index * 17}" text-anchor="middle" '
                f'font-family="{family}" font-size="12" fill="#9fb0cc">{escape(line)}</text>'
            )
        return self

    def label(
        self,
        x: int,
        y: int,
        text: str,
        size: int = 13,
        color: str = "#9fb0cc",
        anchor: str = "middle",
        bold: bool = False,
        mono: bool = False,
    ) -> Svg:
        family = MONO if mono else FONT
        weight = "700" if bold else "400"
        self.parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}">{escape(text)}</text>'
        )
        return self

    def arrow(self, x1: int, y1: int, x2: int, y2: int, dashed: bool = False) -> Svg:
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#8fa3bf" stroke-width="1.6"'
            f'{dash} marker-end="url(#arrow)"/>'
        )
        return self

    def path(self, d: str, dashed: bool = False, color: str = "#8fa3bf") -> Svg:
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"{dash} marker-end="url(#arrow)"/>'
        )
        return self

    def rect(self, x: int, y: int, w: int, h: int, color: str = "grey", radius: int = 10) -> Svg:
        bg, border = PALETTE[color]
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{bg}" '
            f'stroke="{border}" stroke-width="1.2" stroke-dasharray="4 3"/>'
        )
        return self

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(self.parts) + "\n</svg>\n"
        path.write_text(content, encoding="utf-8")
        return path


# ----------------------------------------------------------------------
# Диаграммы
# ----------------------------------------------------------------------
def devops_lifecycle() -> Svg:
    """Петля DevOps: 8 этапов по эллипсу и обратная связь «эксплуатация → планирование»."""
    import math

    svg = Svg(900, 560, "Жизненный цикл DevOps")
    svg.label(450, 34, "Жизненный цикл DevOps: бесконечная петля", size=17, color="#e6edf7", bold=True)
    steps = [
        ("Планирование", "бэклог, задачи", "blue"),
        ("Разработка", "git, ревью", "blue"),
        ("Сборка", "CI-пайплайн", "green"),
        ("Тестирование", "unit, e2e", "green"),
        ("Релиз", "артефакты, теги", "orange"),
        ("Деплой", "staging, prod", "orange"),
        ("Эксплуатация", "SRE, алерты", "purple"),
        ("Мониторинг", "SLI/SLO, логи", "purple"),
    ]
    cx, cy, rx, ry = 450, 300, 320, 150
    box_w, box_h = 168, 68
    centers = []
    for index in range(len(steps)):
        angle = -math.pi / 2 + index * (2 * math.pi / len(steps))
        x = cx + rx * math.cos(angle)
        y = cy + ry * math.sin(angle)
        centers.append((x, y))
        title, subtitle, color = steps[index]
        svg.box(int(x - box_w / 2), int(y - box_h / 2), box_w, box_h, title, [subtitle], color)
    # дуги между блоками по часовой стрелке
    for index in range(len(steps)):
        x1, y1 = centers[index]
        x2, y2 = centers[(index + 1) % len(steps)]
        start = (cx + (x1 - cx) * 0.72, cy + (y1 - cy) * 0.72)
        end = (cx + (x2 - cx) * 0.72, cy + (y2 - cy) * 0.72)
        svg.path(
            f"M {start[0]:.0f} {start[1]:.0f} Q {cx} {cy + 40} {end[0]:.0f} {end[1]:.0f}",
            dashed=index == len(steps) - 1,
        )
    # панель в центре, чтобы стрелки не пересекали текст
    svg.parts.append(
        '<rect x="330" y="256" width="240" height="66" rx="12" fill="#0f172a" stroke="#26375c" stroke-width="1.2"/>'
    )
    svg.parts.append(
        f'<text x="450" y="282" text-anchor="middle" font-family="{FONT}" font-size="14" '
        'font-weight="700" fill="#e6edf7">Feedback loop</text>'
    )
    svg.parts.append(
        f'<text x="450" y="304" text-anchor="middle" font-family="{FONT}" font-size="11.5" fill="#9fb0cc">'
        "наблюдения возвращаются в планирование</text>"
    )
    svg.label(450, 516, "Чем короче петля и быстрее обратная связь, тем дешевле изменения и надёжнее продукт", size=13, bold=True)
    svg.label(450, 538, "Метрики скорости петли: lead time, deployment frequency, MTTR, change failure rate (DORA)", size=12)
    return svg


def linux_filesystem() -> Svg:
    svg = Svg(900, 520, "Файловая система Linux")
    svg.label(450, 34, "Иерархия файловой системы (FHS)", size=17, color="#e6edf7", bold=True)
    svg.box(360, 60, 180, 58, "/", ["корень файловой системы"], "blue")
    items = [
        ("/etc", ["конфиги", "nginx.conf"], "green"),
        ("/var", ["логи, кэш", "/var/log"], "green"),
        ("/home", ["данные", "пользов."], "blue"),
        ("/usr", ["бинарники", "/usr/bin"], "blue"),
        ("/opt", ["сторонний", "софт"], "purple"),
        ("/tmp", ["временные", "файлы"], "orange"),
        ("/proc", ["виртуальная", "ФС: процессы"], "purple"),
        ("/dev", ["устройства", "диски"], "grey"),
    ]
    for index, (name, lines, color) in enumerate(items):
        x = 40 + index * 105
        svg.box(x, 180, 95, 76, name, lines, color, mono=False)
        svg.arrow(450, 118, x + 47, 176)
    svg.label(450, 300, "Правило DevOps-инженера: конфиги (/etc) и данные (/var, /home) живут отдельно от кода (/opt, /usr/local)", size=12)
    svg.box(90, 350, 330, 130, "Где смотреть диагностику", [
        "/var/log/syslog, journalctl",
        "/var/log/nginx/error.log",
        "/proc/cpuinfo, /proc/meminfo",
        "df -h, du -sh, mount",
    ], "orange")
    svg.box(480, 350, 330, 130, "Что важно не трогать", [
        "rm -rf / — уничтожает систему",
        "chmod 777 на /etc — дыра в безопасности",
        "правки бинарников в /usr/bin",
        "заполненный / или /var — падение сервисов",
    ], "red")
    return svg


def linux_permissions() -> Svg:
    svg = Svg(880, 420, "Права доступа в Linux")
    svg.label(440, 34, "rwx: кто и что может делать с файлом", size=17, color="#e6edf7", bold=True)
    svg.box(60, 70, 760, 120, "chmod 754 script.sh   →   -rwxr-xr--   владелец: группа: остальные", [
        "7 = 4(r) + 2(w) + 1(x)  — владелец: читает, пишет, исполняет",
        "5 = 4(r) + 1(x)         — группа: читает и исполняет",
        "4 = 4(r)                — остальные: только читают",
    ], "blue", mono=True)
    for index, (title, lines, color) in enumerate([
        ("umask 022", ["новые файлы 644", "каталоги 755"], "green"),
        ("chown user:grp", ["меняет владельца", "нужен sudo"], "orange"),
        ("setfacl -m", ["точечные права", "для нескольких групп"], "purple"),
        ("sudo visudo", ["права без пароля", "только по делу"], "red"),
    ]):
        svg.box(60 + index * 195, 230, 175, 100, title, lines, color)
    svg.label(440, 370, "Проверка: ls -l, id, getfacl, sudo -l  |  Типовая ошибка: chmod 777 вместо группы и ACL", size=12)
    return svg


def networking_osi() -> Svg:
    svg = Svg(900, 520, "Сетевая модель и диагностика")
    svg.label(450, 34, "Стек TCP/IP и инструменты диагностики", size=17, color="#e6edf7", bold=True)
    layers = [
        ("Прикладной", "HTTP, DNS, TLS", "curl -v, dig, openssl s_client", "blue"),
        ("Транспортный", "TCP, UDP, порты", "ss -tulpn, nc -vz, tcpdump", "green"),
        ("Сетевой", "IP, маршрутизация, ICMP", "ip a, ip r, ping, traceroute", "orange"),
        ("Канальный", "Ethernet, ARP, MAC", "ip link, arp -a", "purple"),
    ]
    for index, (name, protocols, tools, color) in enumerate(layers):
        y = 80 + index * 92
        svg.box(60, y, 300, 78, name, [protocols], color)
        svg.box(400, y, 440, 78, tools, [""], color)
        svg.label(620, y + 52, "инструмент диагностики этого уровня", size=11)
    svg.label(450, 460, "Порядок разбора проблемы: DNS → порт → TLS → приложение → логи", size=13, bold=True)
    svg.label(450, 485, "curl -v https://api.example.com  показывает каждый шаг соединения", size=12)
    return svg


def git_branching() -> Svg:
    svg = Svg(900, 460, "Ветвление в Git")
    svg.label(450, 34, "Trunk-based / GitHub Flow: короткие ветки и pull request", size=16, color="#e6edf7", bold=True)
    svg.label(60, 100, "main", anchor="start", bold=True, color="#e6edf7")
    svg.label(60, 200, "feature/*", anchor="start", bold=True, color="#e6edf7")
    svg.label(60, 300, "release/*", anchor="start", bold=True, color="#e6edf7")
    for index in range(6):
        x = 130 + index * 120
        svg.parts.append(f'<circle cx="{x}" cy="95" r="9" fill="#4f9cf9"/>')
        svg.label(x, 70, f"c{index + 1}", size=11)
    svg.parts.append('<line x1="130" y1="95" x2="760" y2="95" stroke="#4f9cf9" stroke-width="2"/>')
    svg.parts.append('<circle cx="250" cy="195" r="9" fill="#3ecf8e"/>')
    svg.parts.append('<line x1="250" y1="195" x2="490" y2="195" stroke="#3ecf8e" stroke-width="2"/>')
    svg.path("M 250 95 C 250 140, 250 160, 250 186")
    svg.path("M 490 195 C 490 160, 490 140, 490 104")
    svg.label(370, 230, "PR + ревью + зелёный CI обязательны", size=12)
    svg.parts.append('<circle cx="610" cy="295" r="9" fill="#f0b429"/>')
    svg.parts.append('<line x1="610" y1="295" x2="760" y2="295" stroke="#f0b429" stroke-width="2"/>')
    svg.path("M 610 95 C 610 180, 610 240, 610 286")
    svg.path("M 760 295 C 800 295, 800 110, 770 100", color="#f0b429")
    svg.label(450, 360, "Правила гигиены: ветка живёт часы-дни, коммит атомарный, сообщение объясняет «почему»", size=12)
    svg.box(70, 380, 340, 60, "git rebase -i", ["чистая история перед ревью"], "purple")
    svg.box(490, 380, 340, 60, "git revert", ["безопасный откат в main"], "orange")
    return svg


def cicd_pipeline() -> Svg:
    svg = Svg(920, 470, "CI/CD конвейер")
    svg.label(460, 34, "Конвейер поставки: от коммита до продакшена", size=17, color="#e6edf7", bold=True)
    stages = [
        ("commit", ["push / PR"], "blue"),
        ("lint+test", ["pytest, ruff"], "green"),
        ("build", ["артефакт, образ"], "green"),
        ("security", ["SAST, SBOM"], "orange"),
        ("staging", ["автотесты e2e"], "orange"),
        ("prod", ["canary, rollout"], "purple"),
        ("monitor", ["SLI/SLO"], "purple"),
    ]
    for index, (name, lines, color) in enumerate(stages):
        x = 30 + index * 126
        svg.box(x, 90, 112, 84, name, lines, color)
        if index:
            svg.arrow(x - 16, 132, x - 4, 132)
    svg.box(40, 230, 400, 170, "Обязательные свойства пайплайна", [
        "быстрый фидбэк: до 10 минут на PR",
        "воспроизводимость: версии пинуются",
        "артефакт собирается один раз",
        "секреты только в vault/секретах CI",
        "падение сборки — блокер для merge",
    ], "blue")
    svg.box(470, 230, 410, 170, "Стратегии деплоя", [
        "Rolling — по частям, дефолт k8s",
        "Blue/Green — два окружения, мгновенный откат",
        "Canary — 5% трафика, затем 100%",
        "Feature flags — релиз без деплоя",
        "Rollback должен быть одной командой",
    ], "green")
    return svg


def docker_layers() -> Svg:
    svg = Svg(900, 520, "Слои образа Docker")
    svg.label(450, 34, "Dockerfile → слои образа → контейнер", size=17, color="#e6edf7", bold=True)
    layers = [
        ("FROM python:3.12-slim", "базовый образ", "grey"),
        ("COPY requirements.txt .", "кэшируется отдельно", "blue"),
        ("RUN pip install -r requirements.txt", "меняется при смене зависимостей", "blue"),
        ("COPY app/ /app", "код меняется часто — сверху", "green"),
        ("RUN useradd -m app && USER app", "непривилегированный пользователь", "orange"),
        ("CMD [\"python\", \"-m\", \"app\"]", "точка входа", "purple"),
    ]
    for index, (code, note, color) in enumerate(layers):
        y = 80 + index * 52
        svg.box(60, y, 480, 44, code, [], color, mono=True)
        svg.label(560, y + 27, note, anchor="start", size=12)
    svg.arrow(600, 430, 600, 380)
    svg.box(560, 440, 300, 60, "docker run / compose up", ["контейнер = слои + writable layer"], "green")
    svg.box(60, 400, 470, 100, "Правила образов", [
        "multi-stage build уменьшает размер в 5-10 раз",
        "не запускать от root, ставить USER",
        "HEALTHCHECK и корректный CMD (exec-форма)",
        ".dockerignore исключает .git, venv, кэши",
    ], "orange")
    return svg


def k8s_architecture() -> Svg:
    svg = Svg(920, 540, "Архитектура Kubernetes")
    svg.label(460, 34, "Кластер Kubernetes: control plane и worker-узлы", size=17, color="#e6edf7", bold=True)
    svg.rect(40, 60, 380, 200, "grey")
    svg.label(230, 84, "Control plane", size=15, bold=True, color="#e6edf7")
    for index, (name, note, color) in enumerate([
        ("kube-apiserver", "точка входа API", "blue"),
        ("etcd", "состояние кластера", "purple"),
        ("scheduler", "выбор узла для pod", "green"),
        ("controller-manager", "следит за desired state", "orange"),
    ]):
        svg.box(60 + (index % 2) * 185, 100 + (index // 2) * 80, 175, 70, name, [note], color)
    svg.rect(470, 60, 410, 200, "grey")
    svg.label(675, 84, "Worker-узел", size=15, bold=True, color="#e6edf7")
    for index, (name, note, color) in enumerate([
        ("kubelet", "запускает контейнеры", "blue"),
        ("kube-proxy", "сетевые правила", "green"),
        ("containerd", "runtime", "purple"),
        ("Pods", "приложение + sidecar", "orange"),
    ]):
        svg.box(490 + (index % 2) * 195, 100 + (index // 2) * 80, 185, 70, name, [note], color)
    svg.arrow(445, 160, 465, 160)
    svg.box(40, 300, 840, 100, "Объекты, которые описывают приложение", [
        "Deployment → ReplicaSet → Pod  |  Service (ClusterIP/NodePort/LoadBalancer)  |  Ingress → роутинг по домену",
        "ConfigMap и Secret → конфигурация  |  HPA → автомасштабирование по CPU/RPS  |  PDB → доступность при обновлении",
    ], "blue")
    svg.box(40, 430, 400, 90, "Проверки живости и готовности", [
        "livenessProbe — перезапуск зависшего pod",
        "readinessProbe — трафик только в здоровый pod",
        "startupProbe — медленный старт",
    ], "green")
    svg.box(470, 430, 410, 90, "Отладка", [
        "kubectl get/describe -n ns",
        "kubectl logs -f, exec -it",
        "kubectl get events --sort-by=.lastTimestamp",
    ], "orange")
    return svg


def iac_flow() -> Svg:
    svg = Svg(900, 470, "Инфраструктура как код")
    svg.label(450, 34, "IaC: Terraform создаёт ресурсы, Ansible настраивает", size=17, color="#e6edf7", bold=True)
    svg.box(60, 90, 220, 110, "Код в Git", ["main.tf, playbook.yml", "ревью и версии"], "blue")
    svg.box(340, 90, 220, 110, "CI: plan", ["terraform plan", "линтеры, tflint"], "green")
    svg.box(620, 90, 220, 110, "Apply", ["создание облака", "идемпотентно"], "orange")
    svg.arrow(285, 145, 335, 145)
    svg.arrow(565, 145, 615, 145)
    svg.box(60, 250, 380, 180, "Terraform: модель состояния", [
        "state хранит карту «код ↔ реальность»",
        "remote backend + блокировка (S3+DynamoDB) — командная работа",
        "terraform plan перед каждым apply",
        "модули для повторно используемых ресурсов",
        "секреты — не в коде, а в переменных окружения",
    ], "blue")
    svg.box(470, 250, 380, 180, "Ansible: конфигурация узлов", [
        "inventory: какие хосты настраиваем",
        "playbook + roles, YAML и Jinja2",
        "идемпотентность: повторный запуск безопасен",
        "check mode: ansible-playbook --check",
        "ansible-vault для секретов",
    ], "green")
    return svg


def aws_cloud() -> Svg:
    svg = Svg(900, 500, "Базовая архитектура в AWS")
    svg.label(450, 34, "Минимальный прод-контур в облаке", size=17, color="#e6edf7", bold=True)
    svg.rect(40, 60, 820, 230, "grey")
    svg.label(450, 84, "VPC 10.0.0.0/16", size=14, color="#e6edf7", bold=True)
    svg.box(60, 100, 230, 80, "Public subnet", ["ALB / NAT Gateway", "bastion"], "green")
    svg.box(320, 100, 240, 80, "Private subnet (app)", ["EC2/ASG или EKS", "выходит в интернет через NAT"], "blue")
    svg.box(590, 100, 250, 80, "Private subnet (data)", ["RDS Multi-AZ", "бэкапы и шифрование"], "purple")
    svg.arrow(295, 140, 315, 140)
    svg.arrow(565, 140, 585, 140)
    svg.box(60, 200, 230, 76, "IAM", ["роли, least privilege", "MFA для админов"], "orange")
    svg.box(320, 200, 240, 76, "S3", ["артефакты, бэкапы", "lifecycle-политики"], "orange")
    svg.box(590, 200, 250, 76, "CloudWatch", ["метрики, логи, алерты"], "orange")
    svg.box(40, 310, 400, 160, "Гигиена стоимости", [
        "rightsizing инстансов по метрикам",
        "Spot/Fargate для некритичных задач",
        "S3 Intelligent-Tiering для бэкапов",
        "budget alert на 80% и 100%",
        "теги: owner, project, env — обязательны",
    ], "green")
    svg.box(470, 310, 390, 160, "Надёжность", [
        "мульти-AZ по умолчанию",
        "IaC вместо кликов в консоли",
        "RTO/RPO зафиксированы и протестированы",
        "restore бэкапа проверяется раз в квартал",
        "плановая игра «погаси AZ» (chaos game)",
    ], "blue")
    return svg


def observability() -> Svg:
    svg = Svg(900, 500, "Наблюдаемость")
    svg.label(450, 34, "Три столпа наблюдаемости и цикл реакции", size=17, color="#e6edf7", bold=True)
    svg.box(50, 80, 250, 130, "Метрики", ["Prometheus, VictoriaMetrics", "counters, gauges, histograms", "RED-метрики: Rate, Errors, Duration"], "blue")
    svg.box(325, 80, 250, 130, "Логи", ["Loki, ELK, CloudWatch", "структурированный JSON", "trace_id для корреляции"], "green")
    svg.box(600, 80, 250, 130, "Трейсы", ["OpenTelemetry, Jaeger", "сквозной путь запроса", "поиск узкого места"], "purple")
    svg.box(50, 250, 380, 120, "Алерты, которые не шумят", [
        "алерт на симптом для пользователя (SLO), а не на каждый чих",
        "runbook в описании алерта",
        "дежурства и эскалации",
        "постмортем без поиска виноватых",
    ], "orange")
    svg.box(470, 250, 380, 120, "SLI / SLO / Error budget", [
        "SLI: измеримая метрика (например, доля успешных запросов)",
        "SLO: цель, например 99.9% за 30 дней",
        "error budget: сколько сбоев допустимо",
        "бюджет исчерпан — только надёжность, без фич",
    ], "green")
    svg.box(50, 395, 800, 80, "Дашборды Grafana", [
        "сначала 4 золотых сигнала: latency, traffic, errors, saturation",
        "затем детализация по сервисам и зависимостям",
        "на дашборде видно, когда сломалось и что изменилось",
    ], "blue")
    return svg


def devsecops() -> Svg:
    svg = Svg(900, 470, "DevSecOps")
    svg.label(450, 34, "Безопасность встроена в конвейер, а не в конце", size=17, color="#e6edf7", bold=True)
    stages = [
        ("Код", ["pre-commit", "gitleaks"], "blue"),
        ("Сборка", ["dependabot", "SBOM"], "green"),
        ("Тест", ["SAST: semgrep", "DAST: ZAP"], "orange"),
        ("Образ", ["trivy scan", "подпись cosign"], "purple"),
        ("Деплой", ["OPA/Gatekeeper", "least privilege"], "blue"),
        ("Эксплуатация", ["audit-логи", "SIEM"], "red"),
    ]
    for index, (name, lines, color) in enumerate(stages):
        svg.box(35 + index * 142, 80, 128, 90, name, lines, color)
        if index:
            svg.arrow(35 + index * 142 - 14, 125, 35 + index * 142 - 4, 125)
    svg.box(40, 210, 400, 200, "Практики на каждый день", [
        "секреты только в vault/secret manager, ротация",
        "принцип least privilege для IAM и RBAC",
        "2FA и короткоживущие токены CI",
        "фиксировать версии базовых образов по digest",
        "проверять SBOM и критичные CVE перед релизом",
        "логировать доступ к данным",
    ], "green")
    svg.box(460, 210, 400, 200, "Как ломают чаще всего", [
        "секрет в git-истории",
        "непривилегированный сервис с root-правами",
        "открытый в интернет порт БД",
        "устаревшая зависимость с CVE",
        "человеческий фактор: фишинг, слабый пароль",
        "избыточные права CI-токена",
    ], "red")
    return svg


def deployment_strategies() -> Svg:
    svg = Svg(900, 470, "Стратегии деплоя")
    svg.label(450, 34, "Как выпускать изменения без простоя", size=17, color="#e6edf7", bold=True)
    cards = [
        ("Rolling update", ["по умолчанию в k8s", "простой = 0 при readiness", "откат: kubectl rollout undo"], "blue"),
        ("Blue / Green", ["два окружения", "переключение трафика", "мгновенный откат"], "green"),
        ("Canary", ["1-5-25-100% трафика", "сравнение метрик", "автооткат по SLO"], "orange"),
        ("Feature flags", ["код уже в проде", "включение по группам", "без релиза"], "purple"),
    ]
    for index, (title, lines, color) in enumerate(cards):
        svg.box(40 + index * 215, 80, 200, 140, title, lines, color)
    svg.box(40, 250, 400, 180, "Что делает релиз безопасным", [
        "миграции БД обратно совместимы (expand/contract)",
        "фича за флагом, если риск высок",
        "проверка health и smoke-тестов после выката",
        "наблюдаемость до релиза, а не после",
        "один ответственный за релиз и окно времени",
    ], "green")
    svg.box(460, 250, 400, 180, "Признаки проблемного процесса", [
        "релиз раз в месяц большого объёма",
        "ручные шаги «по инструкции в wiki»",
        "нет отката — только «чинить вперёд»",
        "никто не знает, что именно задеплоено",
        "тесты после выката вместо до",
    ], "red")
    return svg


def sre_practices() -> Svg:
    svg = Svg(900, 520, "SRE-практики")
    svg.label(450, 34, "Надёжность как инженерная задача", size=17, color="#e6edf7", bold=True)
    svg.box(50, 80, 370, 130, "Инцидент", ["детект → алерт → дежурный", "тriage: влияние на пользователя", "rollback раньше, чем debug"], "red")
    svg.box(480, 80, 370, 130, "Митигация", ["коммуникация в канале", "статус на статус-странице", "после — стабилизация"], "orange")
    svg.box(50, 240, 370, 130, "Постмортем", ["таймлайн без обвинений", "корневые причины", "action items с владельцами"], "blue")
    svg.box(480, 240, 370, 130, "Профилактика", ["автотесты на сценарий", "алерт до отказа", "chaos-эксперименты"], "green")
    svg.box(50, 400, 800, 90, "Три метрики, по которым вас оценят на работе", [
        "MTTD — как быстро замечаем | MTTR — как быстро восстанавливаем | частота инцидентов за квартал",
    ], "purple")
    return svg


def career_roadmap() -> Svg:
    svg = Svg(920, 500, "Дорожная карта DevOps-инженера")
    svg.label(460, 34, "С чего начать и куда расти", size=17, color="#e6edf7", bold=True)
    stages = [
        ("Junior", ["Linux, git, bash", "первый конвейер", "Docker"], "blue", 100),
        ("Middle", ["k8s, Terraform", "облако, мониторинг", "инциденты"], "green", 320),
        ("Senior", ["архитектура", "SLO и стоимость", "менторинг"], "orange", 540),
        ("Lead/Platform", ["Standards, Developer", "Experience, стратегия"], "purple", 760),
    ]
    for name, lines, color, x in stages:
        svg.box(x - 90, 90, 190, 120, name, lines, color)
    for index in range(len(stages) - 1):
        svg.arrow(stages[index][3] + 105, 150, stages[index + 1][3] - 105, 150)
    svg.box(60, 250, 380, 220, "Что показать работодателю", [
        "публичный репозиторий с CI/CD и IaC",
        "развёрнутое демо-приложение в облаке",
        "описанные инциденты и постмортемы",
        "дашборд мониторинга со SLO",
        "сертификат (CKA, AWS SA) — как усилитель, не замена",
    ], "green")
    svg.box(480, 250, 380, 220, "Как учиться эффективно", [
        "каждый день 1 час практики важнее лекций",
        "делайте проект, а не только курсы",
        "читайте SRE Book и документацию инструментов",
        "ведите свой devlog/заметки",
        "разбирайте чужие постмортемы и RFC",
    ], "blue")
    return svg


DIAGRAMS = {
    "devops-lifecycle.svg": devops_lifecycle,
    "linux-filesystem.svg": linux_filesystem,
    "linux-permissions.svg": linux_permissions,
    "networking-stack.svg": networking_osi,
    "git-branching.svg": git_branching,
    "cicd-pipeline.svg": cicd_pipeline,
    "docker-layers.svg": docker_layers,
    "k8s-architecture.svg": k8s_architecture,
    "iac-flow.svg": iac_flow,
    "aws-architecture.svg": aws_cloud,
    "observability.svg": observability,
    "devsecops.svg": devsecops,
    "deployment-strategies.svg": deployment_strategies,
    "sre-practices.svg": sre_practices,
    "career-roadmap.svg": career_roadmap,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Сгенерировать SVG-иллюстрации курса")
    parser.add_argument("--out", default="content/assets/img", help="каталог для файлов")
    args = parser.parse_args()
    out_dir = Path(args.out)
    for name, factory in DIAGRAMS.items():
        path = factory().save(out_dir / name)
        print(f"создан {path} ({path.stat().st_size} байт)")
    print(f"итого: {len(DIAGRAMS)} иллюстраций")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
