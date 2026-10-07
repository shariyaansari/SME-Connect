import React, { useState } from 'react';
import {
  Users,
  Mail,
  UserCheck,
  Shield,
  Clock,
  Plus,
  Info
} from 'lucide-react';


export default function TeamWorkspaceView({
  currentOrg,
  members,
  pendingInvitations,
  onOpenInviteModal,
  onUpdateRole,
  onAcceptInvitation,
  currentUser,
}) {
  const [roleUpdatingId, setRoleUpdatingId] = useState(null);
  const [acceptingToken, setAcceptingToken] = useState(null);

  const handleRoleChange = async (memberId, newRole) => {
    setRoleUpdatingId(memberId);
    try {
      await onUpdateRole(memberId, newRole);
    } finally {
      setRoleUpdatingId(null);
    }
  };

  const handleAccept = async (token) => {
    setAcceptingToken(token);
    try {
      await onAcceptInvitation(token);
    } finally {
      setAcceptingToken(null);
    }
  };

  const isAdmin = currentOrg?.role === 'Admin';

  const roleBadgeClass = (role) => {
    switch (role) {
      case 'Admin':
        return 'warning';
      case 'Editor':
        return 'success';
      case 'Viewer':
      default:
        return 'neutral';
    }
  };

  return (
    <div>
      {/* Screen Title & Single Primary CTA (Hick's Law) */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '20px',
        gap: '16px',
        flexWrap: 'wrap',
      }}>
        <div>
          <h2>Team and workspace</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '2px' }}>
            Manage organization members, access roles, and invitation lifecycles.
          </p>
        </div>

        {/* Exactly one primary CTA on this screen - strictly Admin only */}
        {isAdmin ? (
          <button className="btn-primary" onClick={onOpenInviteModal}>
            <Plus size={15} />
            <span>Invite member</span>
          </button>
        ) : (
          <button
            className="btn-secondary"
            disabled
            title="Only workspace Admins can invite new members"
            style={{ opacity: 0.5, cursor: 'not-allowed', fontSize: '13px' }}
          >
            <Shield size={13} />
            <span>Invite member (Admin only)</span>
          </button>
        )}
      </div>

      {/* 3 Metric Tiles (Miller's Law) */}
      <div className="metric-grid">
        <div className="metric-tile">
          <div className="metric-tile-label">Workspace members</div>
          <div className="metric-tile-value">{members.length}</div>
        </div>
        <div className="metric-tile">
          <div className="metric-tile-label">Assigned roles</div>
          <div className="metric-tile-value">Admin, Editor, Viewer</div>
        </div>
        <div className="metric-tile">
          <div className="metric-tile-label">Pending invitations</div>
          <div className="metric-tile-value">{pendingInvitations.length}</div>
        </div>
      </div>

      {/* Architecture & Invitation Lifecycle Note (Flat surface-1, no border, 8px radius) */}
      <div style={{
        backgroundColor: 'var(--surface-1)',
        borderRadius: '8px',
        padding: '14px 16px',
        marginBottom: '24px',
        borderLeft: '2px solid var(--primary-btn-bg)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <Info size={15} style={{ color: '#388bfd' }} />
          <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>
            Invitation lifecycle architecture
          </span>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45, marginBottom: '10px' }}>
          An invitation can be created for an email address that does not yet have an account. Registration does not automatically create organization membership; membership is created when the user accepts the invitation.
        </p>

        {/* Simple step sequence */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          flexWrap: 'wrap',
          fontSize: '11px',
          color: 'var(--text-muted)',
        }}>
          <span>Admin</span>
          <span>→</span>
          <span>Invite email</span>
          <span>→</span>
          <span style={{ color: 'var(--status-warning-text)' }}>Invitation (pending)</span>
          <span>→</span>
          <span>User registers & logs in</span>
          <span>→</span>
          <span>View pending invitation</span>
          <span>→</span>
          <span>Accept</span>
          <span>→</span>
          <span style={{ color: 'var(--status-success-text)' }}>Membership created</span>
        </div>
      </div>

      {/* Organization Members Section: Dense List Container */}
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <h3>Organization members</h3>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Current workspace: {currentOrg?.name}
          </span>
        </div>

        <div className="list-container">
          {members.map((member) => {
            const isSelf = member.email === currentUser?.email;
            const isUpdating = roleUpdatingId === member.id;

            return (
              <div key={member.id} className="list-row">
                {/* Left: User Icon + Name and Email */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0, paddingRight: '16px' }}>
                  <Users size={18} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>
                        {member.name}
                      </span>
                      {isSelf && (
                        <span style={{
                          fontSize: '11px',
                          color: 'var(--text-muted)',
                          padding: '0 4px',
                          borderRadius: '4px',
                          backgroundColor: 'rgba(255, 255, 255, 0.05)',
                        }}>
                          You
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {member.email}
                    </div>
                  </div>
                </div>

                {/* Right: Role status pill + Role changer */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                  <span className={`status-pill ${roleBadgeClass(member.role)}`}>
                    <Shield size={11} />
                    <span>{member.role}</span>
                  </span>

                  {isAdmin && (
                    <select
                      value={member.role}
                      disabled={isUpdating}
                      onChange={(e) => handleRoleChange(member.id, e.target.value)}
                      className="form-select"
                      style={{
                        fontSize: '12px',
                        padding: '3px 8px',
                        width: '90px',
                      }}
                    >
                      <option value="Admin">Admin</option>
                      <option value="Editor">Editor</option>
                      <option value="Viewer">Viewer</option>
                    </select>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pending Invitations Section */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <h3>Pending invitations</h3>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Invitations waiting for recipient acceptance
          </span>
        </div>

        {pendingInvitations.length === 0 ? (
          <div style={{
            backgroundColor: 'var(--surface-2)',
            border: '1px solid var(--border)',
            borderRadius: '10px',
            padding: '24px 16px',
            textAlign: 'center',
            color: 'var(--text-secondary)',
            fontSize: '13px',
          }}>
            No pending invitations for this account or workspace.
          </div>
        ) : (
          <div className="list-container">
            {pendingInvitations.map((invite) => {
              const isProcessing = acceptingToken === invite.token;

              return (
                <div key={invite.id} className="list-row">
                  {/* Left: Mail icon + Email + Role details */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0, paddingRight: '16px' }}>
                    <Mail size={18} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>
                        {invite.email}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Invited as {invite.role} • Organization ID: {invite.organization_id}
                      </div>
                    </div>
                  </div>

                  {/* Right: Status badge + Accept action button */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                    <span className="status-pill warning">
                      <Clock size={11} />
                      <span>Pending acceptance</span>
                    </span>

                    {invite.token && (
                      <button
                        className="btn-secondary"
                        onClick={() => handleAccept(invite.token)}
                        disabled={isProcessing}
                        style={{ fontSize: '12px', padding: '4px 10px' }}
                      >
                        <UserCheck size={13} className={isProcessing ? 'spinner' : ''} />
                        <span>{isProcessing ? 'Accepting...' : 'Accept invitation'}</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
