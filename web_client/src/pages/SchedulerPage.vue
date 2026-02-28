<script setup>
import { ref, watch, onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { useApi } from '../composables/useApi'
import DynamicForm from '../components/common/DynamicForm.vue'

const api = useApi()
const toast = useToast()
const jobs = ref([])
const showDialog = ref(false)
const loading = ref(true)

const jobSchema = [
  { name: 'name', type: 'text', label: 'Name', required: true },
  { name: 'message', type: 'text', label: 'Message', required: true },
  {
    name: 'type',
    type: 'select',
    label: 'Schedule Type',
    options: [
      { label: 'Interval', value: 'every' },
      { label: 'Cron Expression', value: 'cron' },
      { label: 'One-time', value: 'at' },
    ],
  },
  { name: 'every_seconds', type: 'int', label: 'Interval (seconds)', visible_when: { type: 'every' } },
  { name: 'cron_expr', type: 'text', label: 'Cron Expression', placeholder: '0 9 * * *', visible_when: { type: 'cron' } },
  { name: 'at', type: 'datetime', label: 'Date/Time', visible_when: { type: 'at' } },
]

const newJob = ref({
  name: '',
  message: '',
  type: 'every',
  every_seconds: 3600,
  cron_expr: '',
  at: null,
})

watch(() => newJob.value.type, (val) => {
  if (val === 'at' && !newJob.value.at) {
    newJob.value.at = new Date(Date.now() + 30 * 60 * 1000)
  }
})

function toLocalISO(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

onMounted(loadJobs)

async function loadJobs() {
  try {
    jobs.value = await api.get('/scheduler/jobs')
  } finally {
    loading.value = false
  }
}

async function createJob() {
  const body = {
    name: newJob.value.name,
    message: newJob.value.message,
  }
  if (newJob.value.type === 'every') body.every_seconds = newJob.value.every_seconds
  if (newJob.value.type === 'cron') body.cron_expr = newJob.value.cron_expr
  if (newJob.value.type === 'at' && newJob.value.at) body.at = toLocalISO(newJob.value.at)

  await api.post('/scheduler/jobs', body)
  toast.add({ severity: 'success', summary: 'Created', detail: 'Job created', life: 2000 })
  showDialog.value = false
  newJob.value = { name: '', message: '', type: 'every', every_seconds: 3600, cron_expr: '', at: null }
  await loadJobs()
}

async function removeJob(id) {
  await api.del(`/scheduler/jobs/${id}`)
  toast.add({ severity: 'info', summary: 'Removed', detail: 'Job deleted', life: 2000 })
  await loadJobs()
}

function formatSchedule(job) {
  if (job.schedule.kind === 'cron') return `cron: ${job.schedule.expr}`
  if (job.schedule.kind === 'every') return `every ${job.schedule.every_ms / 1000}s`
  if (job.schedule.kind === 'at') return `at: ${new Date(job.schedule.at_ms).toLocaleString()}`
  return job.schedule.kind
}

function statusSeverity(status) {
  const map = { running: 'success', active: 'success', stopped: 'warn', error: 'danger', pending: 'info' }
  return map[status] || 'secondary'
}
</script>

<template>
  <div class="scheduler-page">
    <div class="page-header">
      <h2>Scheduler</h2>
      <Button label="Add Job" icon="pi pi-plus" size="small" @click="showDialog = true" />
    </div>

    <div v-if="loading" class="page-loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem"></i>
    </div>

    <div v-else class="table-container">
      <DataTable :value="jobs" striped-rows show-gridlines removable-sort>
        <template #empty>
          <div class="empty-state">
            <i class="pi pi-clock" style="font-size: 2rem; color: var(--p-text-muted-color)"></i>
            <p>No scheduled jobs</p>
          </div>
        </template>
        <Column field="name" header="Name" sortable />
        <Column header="Schedule">
          <template #body="{ data }">
            <code class="schedule-code">{{ formatSchedule(data) }}</code>
          </template>
        </Column>
        <Column field="payload.message" header="Message" />
        <Column header="Status">
          <template #body="{ data }">
            <Tag :value="data.state.status" :severity="statusSeverity(data.state.status)" />
          </template>
        </Column>
        <Column field="state.run_count" header="Runs" sortable />
        <Column header="Actions" style="width: 5rem">
          <template #body="{ data }">
            <Button icon="pi pi-trash" severity="danger" text size="small" @click="removeJob(data.id)" />
          </template>
        </Column>
      </DataTable>
    </div>

    <Dialog v-model:visible="showDialog" header="New Job" modal :style="{ width: '500px' }" :breakpoints="{ '768px': '95vw' }">
      <DynamicForm :schema="jobSchema" v-model="newJob" />
      <div class="dialog-footer">
        <Button label="Cancel" severity="secondary" text @click="showDialog = false" />
        <Button label="Create" icon="pi pi-check" @click="createJob" />
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.scheduler-page {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.page-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.table-container {
  padding: 1rem;
}

.schedule-code {
  font-family: 'SF Mono', ui-monospace, monospace;
  font-size: 0.8rem;
  background: var(--p-surface-100);
  padding: 0.2rem 0.5rem;
  border-radius: 0.25rem;
}

.page-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--p-text-muted-color);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--p-text-muted-color);
  gap: 0.75rem;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
</style>
