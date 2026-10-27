import React from 'react';

interface StatusCardProps {
  title: string;
  description: string;
  status: 'ok' | 'unavailable' | 'pending';
}

export default function StatusCard({ title, description, status }: StatusCardProps) {
  return (
    <div className="status-card">
      <div className="card-header">
        <h3 className="card-title">{title}</h3>
        <span className={`status-badge ${status}`}>
          {status}
        </span>
      </div>
      <p className="card-description">{description}</p>
    </div>
  );
}
