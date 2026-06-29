import { Card, CardContent } from "@/components/ui/Card";
import { readDb } from "@/lib/db";
import { ArrowRight, Activity, Database, ShieldCheck } from 'lucide-react';
import Link from 'next/link';

export default async function Home() {
  const db = await readDb();
  const settings = db.settings || {
    institutionName: "Dx Clinical Laboratory",
    tagline: "Excellence in Precision Diagnostics"
  };

  return (
    <div className="max-w-5xl space-y-8 animate-in fade-in duration-500">

      {/* HERO SECTION */}
      <div className="text-center space-y-4 py-12 bg-gradient-to-br from-primary-50 to-white rounded-2xl border border-primary-100 shadow-sm">
        <div className="flex justify-center mb-4">
          <div className="p-3 bg-primary-100 rounded-full">
            <Activity className="w-10 h-10 text-primary-600" />
          </div>
        </div>
        <h1 className="text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight">
          {settings.institutionName}
        </h1>
        <p className="text-2xl text-slate-600 font-light italic">
          &quot;{settings.tagline}&quot;
        </p>
        <div className="text-sm text-slate-400 uppercase tracking-widest font-semibold pt-4">
          Clinical Laboratory Information System
        </div>
      </div>

      {/* QUICK ACTIONS GRID */}
      <div className="grid md:grid-cols-3 gap-6">
        <Card className="hover:shadow-md transition-shadow cursor-default border-t-4 border-t-emerald-500">
          <CardContent className="pt-6">
            <ShieldCheck className="w-8 h-8 text-emerald-500 mb-2" />
            <h3 className="font-bold text-lg mb-1">Secure & Compliant</h3>
            <p className="text-slate-500 text-sm">Role-based access control and full ISO 15189 audit trails ensure data integrity.</p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow cursor-default border-t-4 border-t-blue-500">
          <CardContent className="pt-6">
            <Database className="w-8 h-8 text-blue-500 mb-2" />
            <h3 className="font-bold text-lg mb-1">Centralized Data</h3>
            <p className="text-slate-500 text-sm">Unified patient records, test orders, and results in a single, searchable repository.</p>
          </CardContent>
        </Card>

        <Link href="/dashboard" className="block">
          <Card className="hover:shadow-md transition-shadow border-t-4 border-t-purple-500 group bg-purple-50 hover:bg-purple-100 relative overflow-hidden">
            <div className="absolute right-0 top-0 p-24 bg-purple-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 -translate-y-1/2 translate-x-1/2"></div>
            <CardContent className="pt-6">
              <div className="flex justify-between items-start">
                <Activity className="w-8 h-8 text-purple-600 mb-2" />
                <ArrowRight className="w-5 h-5 text-purple-400 group-hover:translate-x-1 transition-transform" />
              </div>
              <h3 className="font-bold text-lg mb-1 text-purple-900">Go to Dashboard</h3>
              <p className="text-purple-700 text-sm">Access your workspace.</p>
            </CardContent>
          </Card>
        </Link>
      </div>

    </div>
  );
}
