import { navigate } from "../store.js"
import { t } from "../i18n.js"

export const DevModeBanner = {
  name: "DevModeBanner",
  props: {
    hiddenCount: { type: Number, default: 0 },
    devModeOn: { type: Boolean, default: false },
  },
  computed: {
    visible() { return !this.devModeOn && this.hiddenCount > 0 },
    hiddenLabel() {
      const n = String(this.hiddenCount)
      const translated = t("{n} advanced settings hidden.")
      return translated.includes("{n}") ? translated.replace("{n}", n) : `已隐藏 ${n} 项高级设置。`
    },
  },
  methods: {
    tr(key, fallback = key) { return t(key, fallback) },
    unlock() { navigate("/settings/developer") },
  },
  template: `
    <div v-if="visible" class="gx-alert gx-alert--warn" role="status">
      <i class="bi bi-shield-lock gx-alert__icon"></i>
      <div class="gx-alert__body">
        <strong>{{ hiddenLabel }}</strong>
        <span>{{ tr("Want more advanced features or missing a few toggles? Enable Developer Mode whenever you're ready.") }}</span>
      </div>
      <button type="button" class="gx-btn gx-btn--tonal" @click="unlock">{{ tr("Go to Developer Tab") }}</button>
    </div>
  `,
}
