<script setup>
import { computed, onMounted, ref } from 'vue'
import BaseCard from '../components/base/BaseCard.vue'
import BaseInput from '../components/base/BaseInput.vue'
import BaseBtn from '../components/base/BaseBtn.vue'
import { useAuthStore } from '../stores/auth.js'
import api from '../services/api.js'
import { useToast } from 'primevue/usetoast'

const authStore = useAuthStore()
const toast = useToast()

const defaults = () => ({
  display_name: '',
  email: '',
  access_scope: {
    environments: ['production'],
    models: [],
  },
  operator_preferences: {
    alert_channels: {
      in_app: true,
      email: false,
      slack: false,
    },
    alert_min_severity: 'warning',
    quiet_hours: {
      enabled: false,
      start: '22:00',
      end: '07:00',
      timezone: 'UTC',
    },
    dashboard_defaults: {
      window: '24h',
      refresh_seconds: 30,
      segment_filter: 'all',
    },
  },
})

const form = ref(defaults())
const modelScopeCsv = ref('')
const isSaving = ref(false)

const roleLabel = computed(() => {
  const role = authStore.user?.role || 'guest'
  return String(role).toUpperCase()
})

const hydrateFromUser = (user) => {
  const base = defaults()
  const merged = {
    ...base,
    ...user,
    access_scope: {
      ...base.access_scope,
      ...(user?.access_scope || {}),
    },
    operator_preferences: {
      ...base.operator_preferences,
      ...(user?.operator_preferences || {}),
      alert_channels: {
        ...base.operator_preferences.alert_channels,
        ...(user?.operator_preferences?.alert_channels || {}),
      },
      quiet_hours: {
        ...base.operator_preferences.quiet_hours,
        ...(user?.operator_preferences?.quiet_hours || {}),
      },
      dashboard_defaults: {
        ...base.operator_preferences.dashboard_defaults,
        ...(user?.operator_preferences?.dashboard_defaults || {}),
      },
    },
  }
  form.value = merged
  modelScopeCsv.value = (merged.access_scope.models || []).join(', ')
}

onMounted(() => {
  if (authStore.user) {
    hydrateFromUser(authStore.user)
  }
})

const toggleEnv = (env) => {
  const set = new Set(form.value.access_scope.environments || [])
  if (set.has(env)) {
    set.delete(env)
  } else {
    set.add(env)
  }
  const next = Array.from(set)
  form.value.access_scope.environments = next.length ? next : ['production']
}

const saveChanges = async () => {
  isSaving.value = true
  try {
    const models = modelScopeCsv.value
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean)

    const payload = {
      display_name: form.value.display_name,
      email: form.value.email,
      access_scope: {
        environments: form.value.access_scope.environments,
        models,
      },
      operator_preferences: {
        alert_channels: form.value.operator_preferences.alert_channels,
        alert_min_severity: form.value.operator_preferences.alert_min_severity,
        quiet_hours: form.value.operator_preferences.quiet_hours,
        dashboard_defaults: {
          ...form.value.operator_preferences.dashboard_defaults,
          refresh_seconds: Number(form.value.operator_preferences.dashboard_defaults.refresh_seconds || 30),
        },
      },
    }

    const updatedUser = await api.auth.updateProfile(payload)
    if (updatedUser.access_token) {
      authStore.token = updatedUser.access_token
      localStorage.setItem('access_token', updatedUser.access_token)
    }

    authStore.user = updatedUser
    localStorage.setItem('user', JSON.stringify(updatedUser))
    hydrateFromUser(updatedUser)

    toast.add({ severity: 'success', summary: 'Saved', detail: 'Operator profile updated.', life: 2500 })
  } catch (error) {
    console.error('Failed to update profile:', error)
    const detail = error?.response?.data?.detail || 'Failed to update profile settings.'
    toast.add({ severity: 'error', summary: 'Error', detail, life: 3000 })
  } finally {
    isSaving.value = false
  }
}

const handleLogout = async () => {
  await authStore.logout()
}
</script>

<template>
  <div class="max-w-4xl mx-auto space-y-6">
    <div>
      <h1 class="text-3xl font-bold text-white">Operator Profile</h1>
      <p class="text-sm text-slate-400 mt-1">Configure how you monitor models, alerts, and dashboard defaults.</p>
    </div>

    <BaseCard>
      <h2 class="text-xl font-bold text-white mb-4 pb-3 border-b border-white/5">Identity</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <BaseInput v-model="form.display_name" label="Display Name" />
        <BaseInput v-model="form.email" label="Email" type="email" />
      </div>
      <div class="mt-4 text-sm">
        <span class="text-slate-400">Role:</span>
        <span class="ml-2 px-2 py-1 rounded-full border border-cyan-400/30 text-cyan-200 bg-cyan-500/10">{{ roleLabel }}</span>
      </div>
    </BaseCard>

    <BaseCard>
      <h2 class="text-xl font-bold text-white mb-4 pb-3 border-b border-white/5">Access Scope Defaults</h2>
      <div>
        <p class="text-sm text-slate-400 mb-2">Environments</p>
        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            class="scope-chip"
            :class="form.access_scope.environments.includes('production') ? 'scope-chip-active' : 'scope-chip-inactive'"
            @click="toggleEnv('production')"
          >Production</button>
          <button
            type="button"
            class="scope-chip"
            :class="form.access_scope.environments.includes('staging') ? 'scope-chip-active' : 'scope-chip-inactive'"
            @click="toggleEnv('staging')"
          >Staging</button>
          <button
            type="button"
            class="scope-chip"
            :class="form.access_scope.environments.includes('development') ? 'scope-chip-active' : 'scope-chip-inactive'"
            @click="toggleEnv('development')"
          >Development</button>
        </div>
      </div>
      <div class="mt-4">
        <BaseInput v-model="modelScopeCsv" label="Model Scope" placeholder="model-v1, baseline-xgb, cv-prod" />
        <p class="text-xs text-slate-500 mt-1">Comma-separated model IDs. Leave empty for all models.</p>
      </div>
    </BaseCard>

    <BaseCard>
      <h2 class="text-xl font-bold text-white mb-4 pb-3 border-b border-white/5">Alert Preferences</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <label class="toggle-row">
          <span>In-app</span>
          <input v-model="form.operator_preferences.alert_channels.in_app" type="checkbox" />
        </label>
        <label class="toggle-row">
          <span>Email</span>
          <input v-model="form.operator_preferences.alert_channels.email" type="checkbox" />
        </label>
        <label class="toggle-row">
          <span>Slack</span>
          <input v-model="form.operator_preferences.alert_channels.slack" type="checkbox" />
        </label>
      </div>

      <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="flex flex-col gap-2">
          <label class="label">Minimum Severity</label>
          <select v-model="form.operator_preferences.alert_min_severity" class="select">
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
        </div>
        <div class="flex flex-col gap-2">
          <label class="label">Quiet Hours</label>
          <label class="toggle-row">
            <span>Enable Quiet Hours</span>
            <input v-model="form.operator_preferences.quiet_hours.enabled" type="checkbox" />
          </label>
        </div>
      </div>

      <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        <BaseInput v-model="form.operator_preferences.quiet_hours.start" label="Quiet Start" placeholder="22:00" />
        <BaseInput v-model="form.operator_preferences.quiet_hours.end" label="Quiet End" placeholder="07:00" />
        <BaseInput v-model="form.operator_preferences.quiet_hours.timezone" label="Timezone" placeholder="UTC" />
      </div>
    </BaseCard>

    <BaseCard>
      <h2 class="text-xl font-bold text-white mb-4 pb-3 border-b border-white/5">Dashboard Defaults</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label class="label">Time Window</label>
          <select v-model="form.operator_preferences.dashboard_defaults.window" class="select">
            <option value="1h">1h</option>
            <option value="6h">6h</option>
            <option value="24h">24h</option>
            <option value="7d">7d</option>
          </select>
        </div>
        <BaseInput
          v-model="form.operator_preferences.dashboard_defaults.refresh_seconds"
          label="Refresh Interval (sec)"
          type="number"
        />
        <BaseInput v-model="form.operator_preferences.dashboard_defaults.segment_filter" label="Segment Filter" />
      </div>
    </BaseCard>

    <div class="flex items-center justify-between gap-3">
      <BaseBtn variant="danger" @click="handleLogout">Sign Out</BaseBtn>
      <BaseBtn :disabled="isSaving" @click="saveChanges">{{ isSaving ? 'Saving...' : 'Save Operator Settings' }}</BaseBtn>
    </div>
  </div>
</template>

<style scoped>
.scope-chip {
  border-radius: 9999px;
  border: 1px solid;
  font-size: 0.75rem;
  padding: 0.35rem 0.7rem;
  transition: all 180ms ease;
}

.scope-chip-active {
  border-color: rgba(45, 212, 191, 0.5);
  color: #99f6e4;
  background: rgba(15, 118, 110, 0.18);
}

.scope-chip-inactive {
  border-color: rgba(148, 163, 184, 0.3);
  color: #cbd5e1;
  background: rgba(15, 23, 42, 0.5);
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #e2e8f0;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.5rem;
  padding: 0.6rem 0.8rem;
  background: rgba(15, 23, 42, 0.55);
}

.label {
  display: block;
  margin-bottom: 0.4rem;
  margin-left: 0.2rem;
  color: #94a3b8;
  font-size: 0.85rem;
}

.select {
  width: 100%;
  border: 1px solid rgb(51 65 85);
  background: rgb(15 23 42);
  color: rgb(226 232 240);
  border-radius: 0.5rem;
  padding: 0.58rem 0.75rem;
}
</style>
