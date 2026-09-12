export type Environment = 'development' | 'debian'
export type WebsiteType = 'WordPress' | 'PHP' | 'Node.js' | 'Static'
export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface Website { id: string; name: string; domain: string; type: WebsiteType; status: 'Running' | 'Stopped' | 'Installing' | 'Error'; runtime: string; port: number; ssl: boolean; createdAt: string }
export interface SystemProvider { getSystemInfo(): Promise<Record<string, unknown>> }
export interface WebsiteProvider { list(): Promise<Website[]>; create(input: Omit<Website, 'id' | 'createdAt'>): Promise<Website>; delete(id: string): Promise<void>; start(id: string): Promise<Website>; stop(id: string): Promise<Website>; restart(id: string): Promise<Website> }
export interface DatabaseProvider { list(): Promise<unknown[]>; create(input: { name: string; user: string }): Promise<unknown>; delete(id: string): Promise<void> }
export interface FileSystemProvider { list(path: string): Promise<unknown[]>; validatePath(path: string): string }
export interface ServiceProvider { list(): Promise<unknown[]>; restart(name: string): Promise<unknown> }
export interface BackupProvider { list(): Promise<unknown[]>; create(input: { scope: string }): Promise<unknown>; restore(id: string): Promise<unknown> }
export interface SSLProvider { list(): Promise<unknown[]>; issue(domain: string): Promise<unknown> }
export interface FirewallProvider { status(): Promise<unknown>; propose(rule: { port: number; protocol: string }): Promise<unknown> }
export interface CloudflareProvider { status(): Promise<unknown>; connect(hostname: string): Promise<unknown> }
export interface LogProvider { list(input: { source?: string; cursor?: string; limit?: number }): Promise<unknown> }
export interface RabbyHostProviders { environment: Environment; system: SystemProvider; websites: WebsiteProvider; databases: DatabaseProvider; files: FileSystemProvider; services: ServiceProvider; backups: BackupProvider; ssl: SSLProvider; firewall: FirewallProvider; cloudflare: CloudflareProvider; logs: LogProvider }

const now = () => new Date().toISOString()
const demoSites: Website[] = [
  { id: 'demo-blog', name: 'demo-blog', domain: 'demo.local', type: 'WordPress', status: 'Running', runtime: 'PHP 8.3', port: 80, ssl: false, createdAt: now() },
  { id: 'demo-static', name: 'demo-static', domain: 'static.local', type: 'Static', status: 'Running', runtime: 'Nginx', port: 80, ssl: false, createdAt: now() },
]

class DevelopmentWebsiteProvider implements WebsiteProvider {
  private sites = [...demoSites]
  async list() { return [...this.sites] }
  async create(input: Omit<Website, 'id' | 'createdAt'>) { const site = { ...input, id: crypto.randomUUID(), createdAt: now() }; this.sites.unshift(site); return site }
  async delete(id: string) { this.sites = this.sites.filter((site) => site.id !== id) }
  private change(id: string, status: Website['status']) { const site = this.sites.find((item) => item.id === id); if (!site) throw new Error('Website not found'); site.status = status; return { ...site } }
  async start(id: string) { return this.change(id, 'Running') }
  async stop(id: string) { return this.change(id, 'Stopped') }
  async restart(id: string) { return this.change(id, 'Running') }
}

class DevelopmentFileSystemProvider implements FileSystemProvider {
  private root = '/var/www/rabby-host/sites'
  validatePath(path: string) { const candidate = path.startsWith('/') ? path : `${this.root}/${path}`; const normalized = candidate.replaceAll('\\', '/'); if (!normalized.startsWith(`${this.root}/`) || normalized.includes('/../') || normalized.endsWith('/..')) throw new Error('Path is outside the managed sites directory'); return normalized }
  async list(path: string) { return [{ name: path === '/' ? 'sites' : 'public', type: 'directory', path: this.validatePath(path) }] }
}

class DevelopmentUnavailable implements ServiceProvider, DatabaseProvider, SSLProvider, FirewallProvider, CloudflareProvider, LogProvider, SystemProvider {
  async getSystemInfo() { return { environment: 'development', message: 'Real Debian system metrics require DebianProvider' } }
  async list() { return [] }
  async create(input: { name: string; user: string }) { return { id: crypto.randomUUID(), ...input, environment: 'development' } }
  async delete() { return undefined }
  async restart(name: string) { return { name, status: 'unavailable', environment: 'development' } }
  async createBackup(input: { scope: string }) { return { id: crypto.randomUUID(), ...input, status: 'completed' } }
  async restore(id: string) { return { id, status: 'unavailable', message: 'Requires DebianProvider' } }
  async issue(domain: string) { return { domain, status: 'unavailable', message: 'Real certificates require DebianProvider' } }
  async status() { return { status: 'unavailable', environment: 'development' } }
  async propose(rule: { port: number; protocol: string }) { return { ...rule, status: 'proposal-only' } }
  async connect(hostname: string) { return { hostname, status: 'configuration-only' } }
}

export class DebianProviderUnavailableError extends Error { constructor(feature: string) { super(`${feature} requires the DebianProvider and is unavailable in the Vercel development environment.`) } }
export function getProvider(): RabbyHostProviders {
  const unavailable = new DevelopmentUnavailable()
  return { environment: 'development', system: unavailable, websites: new DevelopmentWebsiteProvider(), databases: unavailable, files: new DevelopmentFileSystemProvider(), services: unavailable, backups: { list: () => unavailable.list(), create: (input) => unavailable.createBackup(input), restore: (id) => unavailable.restore(id) }, ssl: unavailable, firewall: unavailable, cloudflare: unavailable, logs: unavailable }
}
