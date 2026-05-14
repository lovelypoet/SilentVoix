import { ref, onUnmounted } from 'vue'
import { useDemoStore } from './stores/demo.js'

export function useWebSocket(url = '/ws/predict') {
  const store = useDemoStore()
  let ws = null
  let reconnectTimer = null
  let reconnectAttempts = 0
  const maxReconnectDelay = 30000
  const status = ref('disconnected')

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return

    status.value = 'connecting'
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const fullUrl = `${protocol}//${host}${url}`

    ws = new WebSocket(fullUrl)

    ws.onopen = () => {
      status.value = 'connected'
      store.setConnected(true)
      reconnectAttempts = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        store.addPrediction(data)
      } catch (e) {
        console.warn('WS parse error:', e)
      }
    }

    ws.onclose = () => {
      status.value = 'disconnected'
      store.setConnected(false)
      scheduleReconnect()
    }

    ws.onerror = () => {
      if (ws) ws.close()
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    const delay = Math.min(1000 * 2 ** reconnectAttempts, maxReconnectDelay)
    reconnectAttempts++
    status.value = `reconnecting (${reconnectAttempts})`
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof data === 'string' ? data : JSON.stringify(data))
      return true
    }
    return false
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
    status.value = 'disconnected'
    store.setConnected(false)
  }

  onUnmounted(() => disconnect())

  return { connect, disconnect, send, status }
}
