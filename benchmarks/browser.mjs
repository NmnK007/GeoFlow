// Node 22+ and an installed Chromium browser. No browser-driver package required.
// node browser.mjs <checkout> <python> <chrome> <scratch-directory> <free-port>
import { spawn, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile } from "node:fs/promises";
import path from "node:path";
import { openSync, closeSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";

const [root, python, chrome, scratch, port] = process.argv.slice(2);
const address = "http://127.0.0.1:" + port;
const processes = [];
let socket;
function launch(executable, args, env = process.env) {
  const log = openSync(path.join(scratch, path.basename(executable) + ".log"), "a");
  const child = spawn(executable, args, { cwd: root, env, windowsHide: true, stdio: ["ignore", log, log] });
  closeSync(log);
  processes.push(child);
}
async function until(check, label) {
  const end = Date.now() + 60000;
  while (Date.now() < end) {
    const result = await check();
    if (result) return result;
    await sleep(20);
  }
  throw new Error("Timed out waiting for " + label);
}
try {
  if (await fetch(address + "/_stcore/health").then(() => true).catch(() => false)) throw new Error("Choose an unused loopback port");
  await mkdir(scratch, { recursive: true });
  const profile = await mkdtemp(path.join(scratch, "profile-"));
  launch(python, ["-m", "streamlit", "run", "app.py", "--server.address=127.0.0.1",
    "--server.port=" + port, "--server.headless=true", "--browser.gatherUsageStats=false"],
    { ...process.env, PYTHONPATH: path.resolve(root, "src") });
  await until(() => fetch(address + "/_stcore/health").then(r => r.ok).catch(() => false), "server");
  launch(chrome, ["--headless", "--remote-debugging-port=0", "--disable-extensions",
    "--no-first-run", "--no-default-browser-check", "--user-data-dir=" + profile, "about:blank"]);
  const devPort = await until(() => readFile(path.join(profile, "DevToolsActivePort"), "utf8")
    .then(s => s.split(/\r?\n/)[0]).catch(() => false), "Chromium");
  const pages = await (await fetch("http://127.0.0.1:" + devPort + "/json/list")).json();
  socket = new WebSocket(pages.find(p => p.type === "page").webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let sequence = 0;
  const pending = new Map();
  socket.onmessage = ({data}) => {
    const msg = JSON.parse(data);
    if (msg.method === "Runtime.exceptionThrown") console.error(msg.params.exceptionDetails.exception?.description);
    if (msg.method === "Network.loadingFailed") console.error(msg.params.errorText);
    if (msg.method === "Network.webSocketFrameError") console.error(msg.params.errorMessage);
    if (pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  };
  async function command(method, params = {}) {
    const id = ++sequence;
    const reply = new Promise(resolve => pending.set(id, resolve));
    socket.send(JSON.stringify({ id, method, params }));
    const msg = await reply;
    if (msg.error) throw new Error(JSON.stringify(msg.error));
    return msg.result;
  }
  async function evaluate(expression) {
    const result = await command("Runtime.evaluate", { expression, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
    return result.result.value;
  }
  const button = "[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Run Simulation')";
  const images = "[...document.querySelectorAll('[data-testid=stImage] img')].filter(i=>i.complete && i.naturalWidth)";
  await command("Runtime.enable");
  await command("Network.enable");
  const start = performance.now();
  await command("Page.navigate", { url: address });
  try {
    await until(() => evaluate("Boolean(" + button + ")"), "Run Simulation");
  } catch (error) {
    console.error(await evaluate("JSON.stringify({url:location.href,title:document.title,text:document.body.innerText.slice(0,1600),buttons:[...document.querySelectorAll('button')].map(b=>b.innerText)})"));
    throw error;
  }
  const ready = performance.now();
  await evaluate(button + ".click()");
  await until(() => evaluate(images + ".length >= 2"), "both plots");
  const displayed = performance.now();
  const snapshots = [];
  for (let i = 0; i < 3; i++) {
    const slider = "document.querySelector('input[type=range], [role=slider]')";
    if (!await evaluate("Boolean(" + slider + ")")) {
      throw new Error(await evaluate("document.querySelector('[data-testid=stSlider]')?.outerHTML.slice(0,3500) ?? document.body.innerText.slice(-1000)"));
    }
    await evaluate(slider + ".focus()");
    const firstMap = "((i) => i && i.complete && i.naturalWidth && i.currentSrc)(document.querySelector('[data-testid=stImage] img'))";
    const before = await evaluate(firstMap);
    const t = performance.now();
    for (const type of ["keyDown", "keyUp"]) {
      await command("Input.dispatchKeyEvent", { type, key: "ArrowRight", code: "ArrowRight", windowsVirtualKeyCode: 39 });
    }
    await until(() => evaluate(firstMap).then(src => src && src !== before), "updated snapshot");
    snapshots.push(performance.now() - t);
  }
  await command("Performance.enable");
  const { metrics } = await command("Performance.getMetrics");
  const heap = metrics.find(row => row.name === "JSHeapUsedSize").value / 2 ** 20;
  console.log(JSON.stringify({ navigation_to_controls_ms: ready-start, run_to_images_ms: displayed-ready, snapshot_to_image_ms: snapshots, browser_heap_mib: heap }));
  socket.send(JSON.stringify({ id: ++sequence, method: "Browser.close" }));
  await sleep(250);
} finally {
  socket?.close();
  for (const child of processes.reverse()) {
    if (child.exitCode !== null || child.signalCode !== null) continue;
    if (process.platform === "win32" && child.pid) {
      // The Windows venv launcher can own a separate interpreter process.
      spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
    } else {
      child.kill();
    }
  }
}
