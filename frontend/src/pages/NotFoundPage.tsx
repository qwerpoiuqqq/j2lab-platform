import { Link } from 'react-router-dom';
import Button from '@/components/common/Button';

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <h1 className="text-6xl font-bold text-gray-300 mb-4">404</h1>
      <p className="text-lg text-gray-600 mb-6">페이지를 찾을 수 없습니다.</p>
      <Link to="/">
        <Button>대시보드로 이동</Button>
      </Link>
    </div>
  );
}
