import { readdir } from 'node:fs/promises'
import path from 'node:path'
import { NextResponse } from 'next/server'

export async function GET() {
  try { const directory = path.join(process.cwd(), 'public', 'compare'); const files = (await readdir(directory)).filter((file) => file.endsWith('.json')); return NextResponse.json({ files }) } catch { return NextResponse.json({ files: [] }) }
}
