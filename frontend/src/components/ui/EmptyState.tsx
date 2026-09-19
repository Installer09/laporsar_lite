import { FileQuestion } from 'lucide-react';

export function EmptyState({ message = 'Belum ada data' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mb-4">
        <FileQuestion className="w-8 h-8 text-gray-400" />
      </div>
      <h3 className="text-sm font-medium text-gray-900 mb-1">Data Kosong</h3>
      <p className="text-sm text-gray-500">{message}</p>
    </div>
  );
}
