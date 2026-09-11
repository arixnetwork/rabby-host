export type Environment = 'development' | 'debian'
export type WebsiteType = 'WordPress' | 'PHP' | 'Node.js' | 'Static'
export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface Website { id: string; name: string; domain: string; type: WebsiteType; status: string; runtime: string; port: number; ssl: boolean; createdAt: string }
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

export class DebianProviderUnavailableError extends Error { constructor(feature: string) { super(`${feature} requires the DebianProvider and is unavailable in the Vercel development environment.`) } }
export function getProvider(): RabbyHostProviders { throw new DebianProviderUnavailableError('Provider bootstrap') }
