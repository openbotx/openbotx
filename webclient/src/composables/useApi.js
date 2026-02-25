import { useAuthStore } from '../stores/auth'

const BASE_URL = '/api'

export function useApi() {
  function getHeaders(extra = {}) {
    const auth = useAuthStore()
    const headers = { 'Content-Type': 'application/json', ...extra }
    if (auth.token) {
      headers['Authorization'] = `Bearer ${auth.token}`
    }
    return headers
  }

  async function request(path, options = {}) {
    const url = `${BASE_URL}${path}`
    const res = await fetch(url, {
      ...options,
      headers: getHeaders(options.headers),
    })

    if (res.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      throw new Error('Session expired')
    }

    if (!res.ok) {
      const text = await res.text()
      throw new Error(`${res.status}: ${text}`)
    }
    return res.json()
  }

  function get(path) {
    return request(path)
  }

  function post(path, body) {
    return request(path, { method: 'POST', body: JSON.stringify(body) })
  }

  function put(path, body) {
    return request(path, { method: 'PUT', body: JSON.stringify(body) })
  }

  function patch(path, body) {
    return request(path, { method: 'PATCH', body: JSON.stringify(body) })
  }

  function del(path) {
    return request(path, { method: 'DELETE' })
  }

  async function upload(path, files) {
    const form = new FormData()
    files.forEach((f, i) => form.append(`file_${i}`, f))
    const url = `${BASE_URL}${path}`
    const auth = useAuthStore()
    const headers = {}
    if (auth.token) headers['Authorization'] = `Bearer ${auth.token}`
    const res = await fetch(url, { method: 'POST', headers, body: form })
    if (res.status === 401) { auth.logout(); throw new Error('Session expired') }
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
    return res.json()
  }

  return { get, post, put, patch, del, upload }
}
