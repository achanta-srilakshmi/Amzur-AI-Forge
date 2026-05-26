import React from 'react';

// SVG Icon components
const ChatIcon = ({ className = '' }: { className?: string }): React.ReactElement => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3-3-3z" />
  </svg>
);

const PDFIcon = ({ className = '' }: { className?: string }): React.ReactElement => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
  </svg>
);

const DatabaseIcon = ({ className = '' }: { className?: string }): React.ReactElement => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

const ExcelIcon = ({ className = '' }: { className?: string }): React.ReactElement => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
  </svg>
);

const GenerateIcon = ({ className = '' }: { className?: string }): React.ReactElement => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
      d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
);

const ResearchIcon = ({ className = '' }: { className?: string }): React.ReactElement => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
  </svg>
);

const TicTacToeIcon = ({ className = '' }: { className?: string }): React.ReactElement => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 3v18M18 3v18M3 6h18M3 18h18" />
  </svg>
);

const PRReviewIcon = ({ className = '' }: { className?: string }): React.ReactElement => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
  </svg>
);

export const TOOL_ICONS = {
  chat: ChatIcon,
  pdf: PDFIcon,
  database: DatabaseIcon,
  excel: ExcelIcon,
  generate: GenerateIcon,
  research: ResearchIcon,
  tictactoe: TicTacToeIcon,
  prreview: PRReviewIcon,
} as const;

export const TOOL_KEYS = ['chat', 'pdf', 'database', 'excel', 'generate', 'research', 'tictactoe', 'prreview'] as const;
export type ToolKey = typeof TOOL_KEYS[number];

export const TOOL_META: Record<ToolKey, { label: string; color: string; icon: React.FC<{ className?: string }> }> = {
  chat: {
    label: 'Chat',
    color: 'text-blue-600',
    icon: ChatIcon,
  },
  pdf: {
    label: 'PDF',
    color: 'text-orange-500',
    icon: PDFIcon,
  },
  database: {
    label: 'Database',
    color: 'text-purple-600',
    icon: DatabaseIcon,
  },
  excel: {
    label: 'Excel',
    color: 'text-emerald-600',
    icon: ExcelIcon,
  },
  generate: {
    label: 'Generate',
    color: 'text-pink-500',
    icon: GenerateIcon,
  },
  research: {
    label: 'Research',
    color: 'text-teal-600',
    icon: ResearchIcon,
  },
  tictactoe: {
    label: 'Tic Tac Toe',
    color: 'text-rose-500',
    icon: TicTacToeIcon,
  },
  prreview: {
    label: 'PR Review',
    color: 'text-violet-600',
    icon: PRReviewIcon,
  },
};
