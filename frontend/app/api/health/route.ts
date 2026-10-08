import { NextResponse } from 'next/server'
export async function GET(){const endpoint=process.env.TRANSLATION_SERVICE_HEALTH_URL;if(!endpoint)return NextResponse.json({status:'Unknown',reason:'Translation service health URL is not configured'})
 try{const response=await fetch(endpoint,{cache:'no-store',signal:AbortSignal.timeout(3000)});return NextResponse.json({status:response.ok?'Operational':'Degraded'},{status:response.ok?200:503})}catch{return NextResponse.json({status:'Down'},{status:503})}}
