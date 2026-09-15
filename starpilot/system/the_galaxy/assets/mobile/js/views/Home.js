import { api, showSnackbar } from "../api.js"
import { usePolling } from "../composables.js"
import { GalaxyConfirm } from "../components/GalaxyModal.js"
import { t } from "../i18n.js"

const toNum = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0 }
const toInt = (v) => Math.round(toNum(v)).toLocaleString("en-US", { maximumFractionDigits: 0 })
const toDec = (v) => toNum(v).toLocaleString("en-US", { maximumFractionDigits: 1 })
const clamp = (v, min = 0, max = 100) => Math.max(min, Math.min(max, toNum(v)))
const pct = (v) => `${Math.round(clamp(v))}%`

const fmtDuration = (seconds) => {
  const total = Math.max(0, Math.round(toNum(seconds)))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`
}

const fmtBytes = (bytes) => {
  const value = Math.max(0, toNum(bytes))
  if (value >= 2 ** 30) return `${toDec(value / 2 ** 30)} GB`
  if (value >= 2 ** 20) return `${toDec(value / 2 ** 20)} MB`
  return `${toInt(value / 1024)} KB`
}

const dateShort = (d) => d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
const timeShort = (d) => d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
const dateTimeShort = (d) => d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })

function fmtDriveRange(startValue, endValue) {
  if (!startValue) return t("No drives yet")
  const start = new Date(startValue)
  if (Number.isNaN(start.getTime())) return String(startValue)
  const end = new Date(endValue)
  if (Number.isNaN(end.getTime()) || end <= start) return dateTimeShort(start)
  if (start.toDateString() === end.toDateString()) {
    return `${dateShort(start)}, ${timeShort(start)}-${timeShort(end)}`
  }
  return `${dateShort(start)}, ${timeShort(start)}-${dateShort(end)}, ${timeShort(end)}`
}

const driveReady = (drive) => drive?.ignored === true || drive?.attentionKnown !== false
const driveUnit = (drive, fallback = "miles") => drive?.distanceUnit || fallback
const driveSpeedUnit = (drive, unit) => drive?.speedUnit || (unit === "kilometers" ? "kph" : "mph")

const FAVORITE_COLORS = ["#5ec8c8", "#8b6cc5", "#d4a060", "#e05577", "#6cc56e", "#8aa3ff"]
const TOP_MODEL_LIMIT = 3
const WEEK_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((label) => t(label))

function hasPendingWork(dashboard) {
  const analysis = dashboard?.analysis || {}
  const pendingRoutes = Math.max(0, Math.round(toNum(analysis.pendingRoutes)))
  const recent = Array.isArray(dashboard?.recentDrives) ? dashboard.recentDrives : []
  return Boolean(analysis.running) || pendingRoutes > 0 || recent.some((d) => !driveReady(d))
}

const emptyStats = () => ({ drives: 0, distance: 0, hours: 0 })
const emptyDrive = () => ({
  date: "", endDate: "", distance: 0, distanceUnit: "", duration: 0,
  avgSpeed: 0, speedUnit: "", engagedPercent: 0, model: t("Unknown model"),
  distractedMoments: 0, unresponsiveMoments: 0, ignored: false, attentionKnown: true,
})

export const Home = {
  name: "Home",
  data() {
    return {
      status: "loading",
      error: "",
      payload: null,
      unit: "miles",
      keepRefreshing: false,
      togglingKey: "",
    }
  },
  computed: {
    dash() { return this.payload?.dashboard || {} },
    driveStats() { return this.payload?.driveStats || {} },
    software() { return this.payload?.softwareInfo || {} },
    device() { return this.dash.device || {} },
    week() { return this.dash.week || {} },
    storage() { return this.dash.storage || {} },

    hero() {
      const device = this.device
      const online = device.online !== false
      return {
        status: device.status || "Parked",
        text: `${t(device.status || "Parked")} - ${online ? t("device online") : t("device offline")}`,
        online,
      }
    },

    analysis() {
      const analysis = this.dash.analysis || {}
      const pendingRoutes = Math.max(0, Math.round(toNum(analysis.pendingRoutes)))
      const pendingDrives = (this.dash.recentDrives || []).filter((d) => !driveReady(d)).length
      const count = Math.max(pendingRoutes, pendingDrives)
      if (!analysis.running && count <= 0) return null
      const shown = count || Math.max(1, Math.round(toNum(analysis.batchSize)))
      const label = analysis.running
        ? `Analyzing ${shown} ${shown === 1 ? "drive" : "drives"}`
        : `${count} ${count === 1 ? "drive" : "drives"} queued`
      return { label: t(label, label) }
    },

    lastDrive() {
      const drive = this.dash.lastDrive || emptyDrive()
      const ready = driveReady(drive)
      const unit = driveUnit(drive, this.unit)
      return {
        ready,
        range: fmtDriveRange(drive.date, drive.endDate),
        model: drive.model || t("Unknown model"),
        metrics: [
          { value: ready ? toDec(drive.distance) : "...", label: ready ? t(unit, unit) : t("analyzing") },
          { value: fmtDuration(drive.duration), label: t("duration") },
          { value: ready ? toInt(drive.avgSpeed) : "...", label: ready ? t(`${driveSpeedUnit(drive, unit)} avg`) : t("speed") },
          { value: ready ? pct(drive.engagedPercent) : "...", label: t("engaged") },
        ],
        footer: ready
          ? [
              { icon: "bi-eye", text: `${toInt(drive.distractedMoments)} ${t("distracted")}` },
              { icon: "bi-exclamation-triangle", text: `${toInt(drive.unresponsiveMoments)} ${t("unresponsive")}` },
            ]
          : [{ icon: "bi-hourglass-split", text: t("Analyzing stats") }],
      }
    },

    statList() {
      const all = { ...emptyStats(), ...(this.driveStats.all || {}) }
      const week = { ...emptyStats(), ...(this.driveStats.week || {}) }
      const starpilot = { ...emptyStats(), ...(this.driveStats.starpilot || {}) }
      const groups = [
        { title: t("All time"), ...all },
        { title: t("Past week"), ...week },
        { title: "StarPilot", ...starpilot },
      ]
      return groups.map((g) => ({
        title: g.title,
        unit: g.unit || this.unit,
        metrics: [
          { value: toInt(g.drives), label: t("drives") },
          { value: toDec(g.distance), label: t(g.unit || this.unit, g.unit || this.unit) },
          { value: toDec(g.hours), label: t("hours") },
        ],
      }))
    },

    weekView() {
      const days = Array.isArray(this.week.dailyDistance) && this.week.dailyDistance.length
        ? this.week.dailyDistance
        : WEEK_LABELS.map((label) => ({ label, distance: 0 }))
      const maxDistance = Math.max(1, ...days.map((d) => toNum(d.distance)))
      return {
        engaged: pct(this.week.engagedPercent),
        engagedValue: clamp(this.week.engagedPercent),
        unit: this.week.distanceUnit || this.unit,
        metrics: [
          { value: toDec(this.week.distance), label: t(this.week.distanceUnit || this.unit, this.week.distanceUnit || this.unit) },
          { value: toDec(this.week.hours), label: t("hours") },
          { value: toInt(this.week.drives), label: t("drives") },
        ],
        days: days.map((d) => ({
          label: t(d.label, d.label),
          distance: toDec(d.distance),
          height: Math.max(4, (toNum(d.distance) / maxDistance) * 100),
        })),
      }
    },

    recordsList() {
      const r = (record) => ({
        value: record?.value ?? "0",
        detail: record?.detail ?? "",
      })
      const records = this.dash.records || {}
      return [
        { icon: "bi-arrow-right", title: t("Longest drive"), ...r(records.longestDrive) },
        { icon: "bi-check2-circle", title: t("Most-engaged day"), ...r(records.mostEngagedDay) },
        { icon: "bi-graph-up-arrow", title: t("Best week"), ...r(records.bestWeek) },
        { icon: "bi-lightning-charge", title: t("Highest streak"), ...r(records.highestStreak) },
        { icon: "bi-shield-check", title: t("Longest undistracted drive"), ...r(records.longestUndistractedDrive) },
        { icon: "bi-stars", title: t("Clean-drive streak"), ...r(records.cleanDriveStreak) },
      ]
    },

    recentList() {
      const drives = Array.isArray(this.dash.recentDrives) ? this.dash.recentDrives : []
      return drives.map((drive, index) => {
        const ignored = drive?.ignored === true
        const ready = driveReady(drive)
        const unit = driveUnit(drive, this.unit)
        const routeNames = Array.isArray(drive?.routeNames) ? drive.routeNames.filter(Boolean) : []
        const pending = !ready && !ignored
        let distance = ""
        if (ignored) distance = t("Stats excluded")
        else if (pending) distance = t("Analyzing stats")
        else distance = `${toDec(drive.distance)} ${t(unit, unit)}`

        let engaged = ""
        let attentionItems = []
        if (ignored) {
          engaged = t("Excluded")
          attentionItems = [{ icon: "bi-eye-slash", text: t("Ignored from stats") }]
        } else if (pending) {
          engaged = t("Pending")
          attentionItems = [{ icon: "bi-hourglass-split", text: t("Waiting for full route analysis") }]
        } else {
          engaged = `${pct(drive.engagedPercent)} ${t("engaged")}`
          attentionItems = [
            { icon: "bi-eye", text: `${toInt(drive.distractedMoments)} ${t("distracted")}` },
            { icon: "bi-exclamation-triangle", text: `${toInt(drive.unresponsiveMoments)} ${t("unresponsive")}` },
          ]
        }

        return {
          key: drive.name || `${drive.date || ""}-${index}`,
          range: fmtDriveRange(drive.date, drive.endDate),
          model: drive.model || t("Unknown model"),
          ignored,
          pending,
          routeNames,
          distance,
          duration: fmtDuration(drive.duration),
          attentionItems,
          engaged,
          engagedValue: ready && !ignored ? clamp(drive.engagedPercent) : 0,
          canToggle: routeNames.length > 0,
          action: ignored ? "include" : "ignore",
          actionIcon: ignored ? "bi-arrow-counterclockwise" : "bi-eye-slash",
          actionLabel: ignored ? t("Include drive stats") : t("Ignore drive stats"),
          toggleKey: routeNames.join(","),
        }
      })
    },

    modelView() {
      const models = Array.isArray(this.dash.favoriteModels) ? this.dash.favoriteModels : []
      if (models.length === 0) {
        return { hasModels: false, style: "", rows: [] }
      }
      const top = models.slice(0, TOP_MODEL_LIMIT)
      const total = top.reduce((sum, m) => sum + Math.max(1, toNum(m.weight)), 0)
      let start = 0
      const segments = top.map((m, i) => {
        const end = start + (Math.max(1, toNum(m.weight)) / total) * 100
        const seg = `${FAVORITE_COLORS[i]} ${start}% ${end}%`
        start = end
        return seg
      })
      const rows = top.map((m, i) => ({
        color: FAVORITE_COLORS[i],
        name: m.name,
        label: `${toInt(m.drives)} ${t("drives")} ${t("using this model")}`,
      }))
      return { hasModels: true, style: `conic-gradient(${segments.join(", ")})`, rows }
    },

    storageView() {
      const counts = this.storage.segmentCounts || {}
      const summary = this.storage.legacyText
        || `${fmtBytes(this.storage.usedBytes)} ${t("used of")} ${fmtBytes(this.storage.totalBytes)}`
      return {
        summary,
        usedPercent: clamp(this.storage.usedPercent),
        rows: [
          { label: t("Dashcam footage"), value: `${toInt(counts.standard)} ${t("segments")}` },
          { label: t("High-resolution footage"), value: `${toInt(counts.highResolution)} ${t("segments")}` },
          { label: t("Konik footage"), value: `${toInt(counts.alternate)} ${t("segments")}` },
          { label: t("Free space"), value: fmtBytes(this.storage.freeBytes) },
        ],
      }
    },

    vitalsList() {
      const device = this.device
      return [
        { label: t("Status"), value: t(device.status || "Parked") },
        { label: t("LAN IP"), value: device.lanIp || t("unknown") },
        { label: t("Network"), value: t(device.networkName || "No wireless connectivity", device.networkName || "No wireless connectivity") },
        { label: t("Uptime"), value: device.uptimeSeconds == null ? t("unknown") : fmtDuration(device.uptimeSeconds) },
        { label: t("CPU temp"), value: device.cpuTempC == null ? t("unknown") : `${toInt(device.cpuTempC)} C` },
        { label: t("GPU temp"), value: device.gpuTempC == null ? t("unknown") : `${toInt(device.gpuTempC)} C` },
      ]
    },

    softwareList() {
      const info = this.software
      const safeGithub = (v) => (String(v || "").trim().startsWith("https://github.com/") ? String(v).trim() : "")
      const commitHref = safeGithub(info.changelogUrl) || safeGithub(info.commitUrl)
      return [
        { label: t("Branch"), value: info.branchName, href: "" },
        { label: t("Build"), value: info.buildEnvironment, href: "" },
        { label: t("Commit"), value: info.commitHash, href: commitHref },
        { label: t("Version date"), value: info.versionDate, href: "" },
        { label: t("Fork maintainer"), value: info.forkMaintainer, href: "" },
        { label: t("Update available"), value: info.updateAvailable, href: "" },
      ]
    },
  },
  methods: {
    tr(key, fallback = key) { return t(key, fallback) },
    isToggling(routeNames) {
      return this.togglingKey === (routeNames || []).join(",")
    },

    async refresh() {
      if (this.status === "loading") return
      this.applyLoading()
      await this.load()
    },

    applyLoading() {
      this.status = this.payload ? "ready" : "loading"
      this.error = ""
    },

    async load() {
      if (this.refreshing) return
      this.refreshing = true
      if (!this.payload) this.status = "loading"
      this.error = ""
      try {
        const data = await api.getStats()
        if (!data) throw new Error("empty stats payload")
        const payloadUnit = data?.dashboard?.week?.distanceUnit || data?.driveStats?.all?.unit
        this.payload = data
        this.unit = payloadUnit || this.unit || "miles"
        this.status = "ready"
        this.keepRefreshing = hasPendingWork(data?.dashboard || {})
      } catch (err) {
        if (this.payload) {
          showSnackbar(t("Couldn't refresh dashboard."), "error")
        } else {
          this.status = "error"
          this.error = err?.message || String(err)
        }
      } finally {
        this.refreshing = false
      }
    },

    async toggleDriveStats(drive) {
      if (drive.action === "ignore") {
        const ok = await GalaxyConfirm({
          title: t("Ignore this drive's statistics?"),
          message: t("It will no longer affect local weekly totals, records, model usage, engagement, or attention streaks."),
          confirmLabel: t("Ignore"),
        })
        if (!ok) return
      }
      this.togglingKey = drive.toggleKey
      try {
        await api.setDriveStats(drive.action, drive.routeNames)
        await this.load()
      } catch (err) {
        showSnackbar(err?.message || `Unable to ${drive.action} drive statistics.`, "error")
      } finally {
        this.togglingKey = ""
      }
    },
  },
  created() {
    this.poll = usePolling(() => this.load(), { interval: 3500, enabled: () => this.keepRefreshing })
    this.poll.start()
  },
  mounted() { this.load() },
  beforeUnmount() { this.poll?.destroy() },
  template: `
    <div class="dh-view">
      <template v-if="status === 'loading'">
        <div class="gx-loading">{{ tr("Loading dashboard...") }}</div>
      </template>

      <template v-else-if="status === 'error'">
        <section class="gx-card">
          <div class="gx-alert gx-alert--warn" style="border:none; margin:0;">
            <i class="bi bi-exclamation-triangle-fill gx-alert__icon"></i>
            <div class="gx-alert__body">
              <strong>{{ tr("Failed to load dashboard") }}</strong>
              <span>{{ error }}</span>
            </div>
          </div>
          <div style="padding: var(--sp-4);">
            <button type="button" class="gx-btn gx-btn--tonal" @click="refresh"><i class="bi bi-arrow-clockwise"></i> {{ tr("Refresh") }}</button>
          </div>
        </section>
      </template>

      <template v-else>
        <div class="dh-hero">
          <div class="dh-hero__info">
            <h1 class="dh-title">{{ tr("Dashboard") }}</h1>
            <p class="dh-sub">
              <span class="gx-status-dot" :class="hero.online ? 'online' : 'offline'"></span>
              {{ hero.text }}
            </p>
          </div>
          <button type="button" class="gx-btn gx-btn--tonal dh-refresh" :disabled="status === 'loading'" @click="refresh">
            <i class="bi bi-arrow-clockwise"></i> {{ tr("Refresh") }}
          </button>
        </div>

        <div v-if="analysis" class="gx-alert gx-alert--info">
          <i class="bi bi-hourglass-split gx-alert__icon"></i>
          <div class="gx-alert__body"><span>{{ analysis.label }}</span></div>
        </div>

        <section class="gx-card dh-card">
          <div class="dh-card__head"><i class="bi bi-controller"></i><span>{{ tr("Last drive") }}</span></div>
          <div class="dh-body">
            <div class="dh-date">{{ lastDrive.range }}</div>
            <div class="dh-metrics">
              <div v-for="m in lastDrive.metrics" :key="m.label" class="dh-metric">
                <strong>{{ m.value }}</strong><span>{{ m.label }}</span>
              </div>
            </div>
            <div class="dh-tags">
              <span class="dh-tag"><i class="bi bi-cpu"></i>{{ lastDrive.model }}</span>
              <template v-if="lastDrive.ready">
                <span class="dh-tag"><i :class="'bi ' + lastDrive.footer[0].icon"></i>{{ lastDrive.footer[0].text }}</span>
                <span class="dh-tag"><i :class="'bi ' + lastDrive.footer[1].icon"></i>{{ lastDrive.footer[1].text }}</span>
              </template>
              <span v-else class="dh-tag"><i class="bi bi-hourglass-split"></i>{{ tr("Analyzing stats") }}</span>
            </div>
          </div>
        </section>

        <div class="dh-label">{{ tr("Your driving") }}</div>
        <div class="dh-grid">
          <section v-for="stat in statList" :key="stat.title" class="gx-card dh-card dh-stat">
            <div class="dh-card__head"><span>{{ stat.title }}</span></div>
            <div class="dh-body dh-metrics dh-metrics--3">
              <div v-for="m in stat.metrics" :key="m.label" class="dh-metric">
                <strong>{{ m.value }}</strong><span>{{ m.label }}</span>
              </div>
            </div>
          </section>
        </div>

        <div class="dh-grid dh-grid--2">
          <section class="gx-card dh-card">
            <div class="dh-card__head"><i class="bi bi-calendar-week"></i><span>{{ tr("This week") }}</span></div>
            <div class="dh-body">
              <div class="dh-week-top">
                <div class="dh-donut" :style="{ '--dh-value': weekView.engagedValue }">
                  <strong>{{ weekView.engaged }}</strong><span>{{ tr("engaged") }}</span>
                </div>
                <div class="dh-metrics dh-metrics--3">
                  <div v-for="m in weekView.metrics" :key="m.label" class="dh-metric">
                    <strong>{{ m.value }}</strong><span>{{ m.label }}</span>
                  </div>
                </div>
              </div>
              <div class="dh-bars">
                <div v-for="d in weekView.days" :key="d.label" class="dh-bar-day" :title="d.distance">
                  <div class="dh-bar-day__bar" :style="{ height: d.height + '%' }"></div>
                  <span>{{ d.label }}</span>
                </div>
              </div>
            </div>
          </section>

          <section class="gx-card dh-card">
            <div class="dh-card__head"><i class="bi bi-trophy"></i><span>{{ tr("Personal records") }}</span></div>
            <div class="dh-list">
              <div v-for="rec in recordsList" :key="rec.title" class="dh-record">
                <span class="dh-record__icon"><i :class="'bi ' + rec.icon"></i></span>
                <div class="dh-record__body">
                  <span class="dh-record__name">{{ rec.title }}</span>
                  <strong class="dh-record__value">{{ rec.value }}</strong>
                </div>
                <small class="dh-record__detail">{{ rec.detail }}</small>
              </div>
            </div>
          </section>
        </div>

        <section class="gx-card dh-card">
          <div class="dh-card__head"><i class="bi bi-clock-history"></i><span>{{ tr("Recent drives") }}</span></div>
          <template v-if="!recentList.length">
            <div class="gx-empty">{{ tr("No local drives found yet.") }}</div>
          </template>
          <div v-else class="dh-list">
            <article v-for="drive in recentList" :key="drive.key" class="dh-drive" :class="{ 'is-pending': drive.pending, 'is-ignored': drive.ignored }">
              <div class="dh-drive__main">
                <strong>{{ drive.range }}</strong>
                <span>{{ drive.model }}</span>
              </div>
              <div class="dh-drive__meta">
                <span>{{ drive.distance }}</span>
                <span>{{ drive.duration }}</span>
              </div>
              <div class="dh-drive__row">
                <div class="dh-drive__cell">
                  <div class="dh-track"><span :style="{ width: drive.engagedValue + '%' }"></span></div>
                  <span class="dh-drive__engaged" :class="{ 'dh-drive__muted': drive.pending || drive.ignored }">{{ drive.engaged }}</span>
                </div>
                <div class="dh-drive__attention">
                  <span v-for="a in drive.attentionItems" :key="a.text"><i :class="'bi ' + a.icon"></i>{{ a.text }}</span>
                </div>
              </div>
              <button v-if="drive.canToggle" type="button" class="gx-manage-btn dh-drive__action" :disabled="isToggling(drive.routeNames)" @click="toggleDriveStats(drive)">
                <i :class="'bi ' + drive.actionIcon"></i> {{ drive.actionLabel }}
              </button>
            </article>
          </div>
        </section>

        <div class="dh-grid dh-grid--2">
          <section class="gx-card dh-card">
            <div class="dh-card__head"><i class="bi bi-stars"></i><span>{{ tr("Most used models") }}</span></div>
            <div v-if="modelView.hasModels" class="dh-body dh-models">
              <div class="dh-chart-ring" :style="{ backgroundImage: modelView.style }" role="img" aria-label="Model usage share"></div>
              <div class="dh-models__list">
                <div v-for="m in modelView.rows" :key="m.name" class="dh-model">
                  <span class="dh-swatch" :style="{ background: m.color }"></span>
                  <div class="dh-model__body">
                    <strong>{{ m.name }}</strong>
                    <small>{{ m.label }}</small>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="gx-empty">{{ tr("No model usage recorded yet.") }}</div>
          </section>

          <section class="gx-card dh-card">
            <div class="dh-card__head"><i class="bi bi-box"></i><span>{{ tr("Storage") }}</span></div>
            <div class="dh-list">
              <div class="gx-row dh-row--stack" style="cursor:default;">
                <p class="dh-muted" style="margin:0;">{{ storageView.summary }}</p>
                <div class="dh-track dh-track--lg"><span :style="{ width: storageView.usedPercent + '%' }"></span></div>
              </div>
              <div v-for="row in storageView.rows" :key="row.label" class="gx-row">
                <span class="gx-row__label">{{ row.label }}</span>
                <span class="gx-row__value">{{ row.value }}</span>
              </div>
            </div>
          </section>
        </div>

        <div class="dh-label">{{ tr("Your device") }}</div>
        <div class="dh-grid dh-grid--2">
          <section class="gx-card dh-card">
            <div class="dh-card__head"><i class="bi bi-cpu"></i><span>{{ tr("Vitals") }}</span></div>
            <div class="dh-list">
              <div v-for="v in vitalsList" :key="v.label" class="gx-row">
                <span class="gx-row__label">{{ v.label }}</span>
                <span class="gx-row__value">{{ v.value }}</span>
              </div>
            </div>
          </section>

          <section class="gx-card dh-card">
            <div class="dh-card__head"><i class="bi bi-star"></i><span>{{ tr("Software") }}</span></div>
            <div class="dh-list">
              <div v-for="row in softwareList" :key="row.label" class="gx-row">
                <span class="gx-row__label">{{ row.label }}</span>
                <span class="gx-row__value dh-software"><a v-if="row.href" :href="row.href" target="_blank" rel="noopener noreferrer">{{ row.value || 'unknown' }}</a><template v-else>{{ row.value || 'unknown' }}</template></span>
              </div>
            </div>
          </section>
        </div>
      </template>
    </div>
  `,
}
