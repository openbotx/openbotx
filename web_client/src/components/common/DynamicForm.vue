<script setup>
import { computed } from 'vue'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Password from 'primevue/password'
import ToggleSwitch from 'primevue/toggleswitch'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import ColorPicker from 'primevue/colorpicker'

const props = defineProps({
  schema: { type: Array, required: true },
  modelValue: { type: Object, required: true },
  references: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:modelValue'])

function update(name, value) {
  emit('update:modelValue', { ...props.modelValue, [name]: value })
}

function isVisible(field) {
  if (!field.visible_when) return true
  for (const [key, expected] of Object.entries(field.visible_when)) {
    const actual = props.modelValue[key]
    if (Array.isArray(expected)) {
      if (!expected.includes(actual)) return false
    } else {
      if (actual !== expected) return false
    }
  }
  return true
}

const visibleFields = computed(() => props.schema.filter(isVisible))

function humanize(name) {
  return name.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function refOptions(type) {
  const items = props.references[type + 's'] || []
  return [{ label: '(none)', value: '' }, ...items.map(n => ({ label: humanize(n), value: n }))]
}
</script>

<template>
  <div class="dynamic-form">
    <div v-for="field in visibleFields" :key="field.name" class="form-group">
      <label>
        {{ field.label }}
        <span v-if="field.required" class="required">*</span>
      </label>

      <!-- text -->
      <InputText
        v-if="field.type === 'text' || field.type === 'email'"
        :model-value="modelValue[field.name] ?? ''"
        @update:model-value="update(field.name, $event)"
        :type="field.type === 'email' ? 'email' : 'text'"
        :placeholder="field.placeholder || ''"
        class="w-full"
      />

      <!-- int -->
      <InputNumber
        v-else-if="field.type === 'int'"
        :model-value="modelValue[field.name] ?? 0"
        @update:model-value="update(field.name, $event)"
        :useGrouping="false"
        class="w-full"
      />

      <!-- float -->
      <InputNumber
        v-else-if="field.type === 'float'"
        :model-value="modelValue[field.name] ?? 0"
        @update:model-value="update(field.name, $event)"
        :min-fraction-digits="1"
        class="w-full"
      />

      <!-- bool -->
      <ToggleSwitch
        v-else-if="field.type === 'bool'"
        :model-value="modelValue[field.name] ?? false"
        @update:model-value="update(field.name, $event)"
      />

      <!-- secret -->
      <Password
        v-else-if="field.type === 'secret'"
        :model-value="modelValue[field.name] ?? ''"
        @update:model-value="update(field.name, $event)"
        :feedback="false"
        toggleMask
        :placeholder="field.placeholder || 'Leave empty to keep current'"
        class="w-full"
        inputClass="w-full"
        :inputProps="{ autocomplete: 'off', 'data-1p-ignore': '' }"
      />

      <!-- long-text -->
      <Textarea
        v-else-if="field.type === 'long-text'"
        :model-value="modelValue[field.name] ?? ''"
        @update:model-value="update(field.name, $event)"
        :placeholder="field.placeholder || ''"
        rows="4"
        class="w-full"
      />

      <!-- select -->
      <Select
        v-else-if="field.type === 'select'"
        :model-value="modelValue[field.name] ?? ''"
        @update:model-value="update(field.name, $event)"
        :options="field.options || []"
        option-label="label"
        option-value="value"
        class="w-full"
      />

      <!-- credential -->
      <Select
        v-else-if="field.type === 'credential'"
        :model-value="modelValue[field.name] ?? ''"
        @update:model-value="update(field.name, $event)"
        :options="refOptions('credential')"
        option-label="label"
        option-value="value"
        class="w-full"
      />

      <!-- provider -->
      <Select
        v-else-if="field.type === 'provider'"
        :model-value="modelValue[field.name] ?? ''"
        @update:model-value="update(field.name, $event)"
        :options="refOptions('provider')"
        option-label="label"
        option-value="value"
        class="w-full"
      />

      <!-- datetime -->
      <DatePicker
        v-else-if="field.type === 'datetime'"
        :model-value="modelValue[field.name]"
        @update:model-value="update(field.name, $event)"
        showTime
        hourFormat="24"
        showIcon
        fluid
        dateFormat="yy-mm-dd"
      />

      <!-- date -->
      <DatePicker
        v-else-if="field.type === 'date'"
        :model-value="modelValue[field.name]"
        @update:model-value="update(field.name, $event)"
        showIcon
        fluid
        dateFormat="yy-mm-dd"
      />

      <!-- time -->
      <DatePicker
        v-else-if="field.type === 'time'"
        :model-value="modelValue[field.name]"
        @update:model-value="update(field.name, $event)"
        timeOnly
        hourFormat="24"
        showIcon
        fluid
      />

      <!-- color -->
      <ColorPicker
        v-else-if="field.type === 'color'"
        :model-value="modelValue[field.name] ?? ''"
        @update:model-value="update(field.name, $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.dynamic-form .form-group {
  margin-bottom: 1rem;
}

.dynamic-form .form-group label {
  display: block;
  margin-bottom: 0.4rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.dynamic-form .required {
  color: var(--p-red-500);
  margin-left: 0.15rem;
}
</style>
