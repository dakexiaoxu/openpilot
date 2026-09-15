import { navigate, toolHref } from "../store.js"
import { t } from "../i18n.js"

const TOOLS = [
  { name: "Bluetooth", link: "/bluetooth", icon: "bi-bluetooth", desc: "Pair devices, controllers, & audio" },
  { name: "Cameras & Monitoring", link: "/cameras", icon: "bi-camera-video", desc: "Sentry, PiP side camera, & V-ASM spot monitor" },
  { name: "Galaxy & App Install", link: "/galaxy", icon: "bi-globe2", desc: "Remote access, pairing, & app install" },  
  { name: "Logs & Diagnostics", link: "/logs", icon: "bi-exclamation-triangle", desc: "Error logs, tmux, troubleshoot" },
  { name: "Model Manager", link: "/manage_models", icon: "bi-cpu", desc: "Install/swap models" },
  { name: "Model Laboratory", link: "/model_laboratory", icon: "bi-bezier2", desc: "Pair lateral and longitudinal models" },
  { name: "Navigation & Maps", link: "/navigation", icon: "bi-map", desc: "Offline maps & destinations" },
  { name: "System Tools", link: "/system", icon: "bi-arrow-repeat", desc: "Backup, restore, updates" },
  { name: "Theme Maker", link: "/theme_maker", icon: "bi-palette-fill", desc: "Customize the look" },
  { name: "Tuning, Plots & Testing", link: "/tuning", icon: "bi-sign-turn-right", desc: "Steering & speed tuning, live plots, testing grounds" },
  { name: "Vehicle Controls", link: "/vehicle", icon: "bi-car-front", desc: "Vehicle features" },
].sort((a, b) => a.name.localeCompare(b.name))

export const Tools = {
  name: "Tools",
  data() { return { TOOLS } },
  methods: {
    tr(key, fallback = key) { return t(key, fallback) },
    open(tool) {
      navigate(toolHref(tool.link))
    },
  },
  template: `
    <div>
      <h2 style="margin-top:0;">{{ tr("Tools") }}</h2>
      <div class="gx-grid">
        <button v-for="tool in TOOLS" :key="tool.link" type="button" class="gx-tile" @click="open(tool)">
          <i class="bi" :class="tool.icon"></i>
          <span>{{ tr(tool.name, tool.name) }}</span>
          <small style="color: var(--text-muted);">{{ tr(tool.desc, tool.desc) }}</small>
        </button>
      </div>
    </div>
  `,
}
