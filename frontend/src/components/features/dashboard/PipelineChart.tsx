import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { PipelineOverview } from '@/types';
import { getPipelineStageLabel } from '@/utils/format';

interface PipelineChartProps {
  data: PipelineOverview[];
}

export default function PipelineChart({ data }: PipelineChartProps) {
  const chartData = data.map((item) => ({
    ...item,
    label: getPipelineStageLabel(item.stage),
  }));

  return (
    <div className="bg-surface rounded-xl border border-border p-5">
      <h3 className="text-base font-semibold text-gray-100 mb-4">
        파이프라인 현황
      </h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#323542" />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              angle={-30}
              textAnchor="end"
              height={60}
            />
            <YAxis tick={{ fontSize: 12, fill: '#9ca3af' }} />
            <Tooltip
              contentStyle={{
                borderRadius: '8px',
                border: '1px solid #323542',
                backgroundColor: '#1e2028',
                color: '#e5e7eb',
              }}
            />
            <Bar
              dataKey="count"
              fill="#06b6d4"
              radius={[4, 4, 0, 0]}
              name="건수"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
