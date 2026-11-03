import { onBeforeUnmount, ref } from "vue";

export type StreamStatus = "connecting" | "live" | "paused" | "disconnected";

export interface StreamHandlers {
  onMessage: (data: string, event: string) => void;
  onError?: (message: string) => void;
  onDone?: (data: string) => void;
}

/**
 * SSE 组合式函数：自动重连（指数退避，最长 15 秒），卸载时关闭。
 * 连接状态与最后接收时间暴露给页面，页面不得把"已断开"显示成"实时"。
 */
export function useEventStream(url: () => string, handlers: StreamHandlers) {
  const status = ref<StreamStatus>("disconnected");
  const lastReceived = ref<Date | null>(null);
  let source: EventSource | null = null;
  let retry = 0;
  let timer: number | undefined;
  let paused = false;

  function close() {
    source?.close();
    source = null;
  }

  function scheduleReconnect() {
    const delay = Math.min(1000 * 2 ** retry, 15000);
    retry += 1;
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(connect, delay);
  }

  function connect() {
    close();
    status.value = "connecting";
    source = new EventSource(url());

    source.onopen = () => {
      retry = 0;
      status.value = paused ? "paused" : "live";
    };

    source.addEventListener("log", (event) => {
      lastReceived.value = new Date();
      if (paused) return;
      handlers.onMessage((event as MessageEvent<string>).data, "log");
    });

    source.addEventListener("done", (event) => {
      lastReceived.value = new Date();
      handlers.onDone?.((event as MessageEvent<string>).data);
      close();
      status.value = paused ? "paused" : "disconnected";
    });

    source.onerror = () => {
      close();
      status.value = paused ? "paused" : "disconnected";
      handlers.onError?.("连接断开，正在重连");
      if (!paused) scheduleReconnect();
    };
  }

  function pause() {
    paused = true;
    status.value = "paused";
  }

  function resume() {
    paused = false;
    if (source && source.readyState === EventSource.OPEN) {
      status.value = "live";
    } else if (!source) {
      connect();
    }
  }

  onBeforeUnmount(() => {
    close();
    if (timer) window.clearTimeout(timer);
  });

  return { status, lastReceived, connect, close, pause, resume };
}
