import { BluetoothPanel } from "../components/BluetoothPanel.js"
import { WheelControls } from "../components/WheelControls.js"
import { GalaxySection } from "../components/GalaxySection.js"
import { GalaxyTabs } from "../components/GalaxyTabs.js"
import { useTabRouting } from "../composables.js"
import { t } from "../i18n.js"

const TABS = {
  bluetooth: "Bluetooth",
  controllers: "Controllers",
}

export const Bluetooth = {
  name: "Bluetooth",
  components: { BluetoothPanel, WheelControls, GalaxySection, GalaxyTabs },
  setup() {
    return useTabRouting("/bluetooth", { bluetooth: "bluetooth", controllers: "controllers" })
  },
  data() { return { TABS } },
  methods: { tr(key, fallback = key) { return t(key, fallback) } },
  template: `
    <div class="gx-view">
      <h2 style="margin-top:0;">{{ tr("Bluetooth") }}</h2>
      <GalaxyTabs :items="TABS" :active="tab" @select="selectTab" />

      <template v-if="tab === 'bluetooth'">
        <GalaxySection title="Bluetooth Devices" icon="bi-bluetooth" :collapsible="false">
          <BluetoothPanel />
        </GalaxySection>
      </template>

      <template v-else>
        <WheelControls />
      </template>
    </div>
  `,
}
