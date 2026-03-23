export default function DeadlineBatchPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">마감 일괄 처리</h1>
        <p className="mt-1 text-sm text-gray-400">
          입금확인 후 마감 시간이 지난 접수건을 일괄 처리합니다.
        </p>
      </div>
      <div className="bg-surface rounded-xl border border-border p-8 text-center">
        <p className="text-gray-400">이 기능은 스케줄러에 의해 자동으로 처리됩니다.</p>
        <p className="text-sm text-gray-500 mt-2">수동 트리거가 필요한 경우 관리자에게 문의하세요.</p>
      </div>
    </div>
  );
}
