import { t } from "../i18n.js"

export const GalaxyTabs = {
  name: "GalaxyTabs",
  props: {
    items: { type: Object, required: true },
    active: { type: String, default: "" },
  },
  emits: ["select"],
  methods: {
    tr(key, fallback = key) { return t(key, fallback) },
  },
  template: `
    <nav class="gx-tabs" role="tablist" :aria-label="tr('View sections')">
      <button v-for="(label, key) in items" :key="key" type="button" role="tab"
        :aria-selected="active === key ? 'true' : 'false'"
        class="gx-tab" :class="{ active: active === key }"
        @click="$emit('select', key)">{{ tr(label, label) }}</button>
    </nav>
  `,
}
