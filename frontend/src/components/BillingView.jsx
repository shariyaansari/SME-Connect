import React, { useState, useEffect, useCallback } from 'react';
import {
  CreditCard,
  CheckCircle2,
  AlertCircle,
  Zap,
  TrendingUp,
  ShieldCheck,
  Calendar,
  Layers,
  ArrowUpRight,
  Info,
  Clock,
  Check,
  Sparkles,
} from 'lucide-react';
import { api } from '../api';

export default function BillingView({ currentOrg, currentUser, onNavigateWorkflows }) {
  const [loading, setLoading] = useState(true);
  const [plans, setPlans] = useState([]);
  const [billingData, setBillingData] = useState(null);
  const [billingCycle, setBillingCycle] = useState('monthly'); // 'monthly' | 'annual'
  const [currency, setCurrency] = useState('usd'); // 'usd' | 'inr'
  const [modalPlan, setModalPlan] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [notice, setNotice] = useState(null);

  const isAdmin = currentOrg?.role === 'Admin';

  const loadBillingInfo = useCallback(async () => {
    try {
      setLoading(true);
      const [catalogRes, subscriptionRes] = await Promise.all([
        api.getPlans(),
        api.getSubscription(currentOrg?.id),
      ]);
      setPlans(catalogRes.plans || []);
      setBillingData(subscriptionRes);
      if (subscriptionRes?.subscription?.billing_cycle) {
        setBillingCycle(subscriptionRes.subscription.billing_cycle);
      }
    } catch (err) {
      console.error('Failed to load billing information:', err);
      setNotice({ type: 'error', message: err.message || 'Failed to load billing details' });
    } finally {
      setLoading(false);
    }
  }, [currentOrg?.id]);

  useEffect(() => {
    loadBillingInfo();
  }, [loadBillingInfo]);

  const handleSelectPlan = (plan) => {
    if (!isAdmin) {
      setNotice({
        type: 'warning',
        message: 'Only workspace Admins can upgrade or modify the subscription plan.',
      });
      return;
    }
    setModalPlan(plan);
  };

  const handleConfirmPlanChange = async () => {
    if (!modalPlan) return;
    try {
      setSubmitting(true);
      await api.updateSubscription(
        {
          plan_tier: modalPlan.tier,
          billing_cycle: billingCycle,
        },
        currentOrg?.id
      );
      setModalPlan(null);
      setNotice({
        type: 'success',
        message: `Successfully switched to ${modalPlan.name} plan! Your active workflow limit has been updated.`,
      });
      await loadBillingInfo();
    } catch (err) {
      console.error('Failed to change plan:', err);
      setNotice({ type: 'error', message: err.message || 'Failed to update subscription' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelSubscription = async () => {
    if (!isAdmin) return;
    if (
      !window.confirm(
        'Are you sure you want to schedule cancellation? Your active workflows will remain published until the end of the current billing period.'
      )
    ) {
      return;
    }
    try {
      setCanceling(true);
      const res = await api.cancelSubscription(currentOrg?.id);
      setNotice({
        type: 'info',
        message: res.message || 'Subscription cancellation scheduled.',
      });
      await loadBillingInfo();
    } catch (err) {
      console.error('Failed to cancel subscription:', err);
      setNotice({ type: 'error', message: err.message || 'Failed to cancel subscription' });
    } finally {
      setCanceling(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '360px', gap: '12px' }}>
        <div className="spinner" style={{ width: '28px', height: '28px' }} />
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Loading subscription and workflow usage...</p>
      </div>
    );
  }

  const subscription = billingData?.subscription;
  const currentPlanTier = subscription?.plan_tier || 'free';
  const usage = billingData?.usage || {
    active_workflows: 0,
    max_active_workflows: 2,
    usage_percentage: 0,
    is_limit_reached: false,
    remaining_slots: 2,
    draft_workflows: 0,
    paused_workflows: 0,
    total_workflows: 0,
  };

  const isUnlimited = usage.max_active_workflows === null || usage.max_active_workflows === undefined;
  const usagePct = isUnlimited ? 0 : Math.min(100, usage.usage_percentage);

  return (
    <div style={{ maxWidth: '1160px', margin: '0 auto', padding: '8px 0 60px' }}>
      {/* Notice Banner */}
      {notice && (
        <div
          style={{
            marginBottom: '20px',
            padding: '12px 16px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            backgroundColor:
              notice.type === 'error'
                ? 'var(--status-error-bg, #fee2e2)'
                : notice.type === 'warning'
                ? 'var(--status-warning-bg, #fef3c7)'
                : 'var(--status-success-bg, #dcfce7)',
            color:
              notice.type === 'error'
                ? 'var(--status-error-text, #991b1b)'
                : notice.type === 'warning'
                ? 'var(--status-warning-text, #92400e)'
                : 'var(--status-success-text, #166534)',
            border: '1px solid currentColor',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px' }}>
            {notice.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
            <span>{notice.message}</span>
          </div>
          <button
            onClick={() => setNotice(null)}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'inherit',
              fontSize: '18px',
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* Hero Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Billing & Subscription
              </h1>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  backgroundColor: 'var(--status-neutral-bg, #e2e8f0)',
                  color: 'var(--text-secondary)',
                }}
              >
                Module 9
              </span>
            </div>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: 0 }}>
              Flat, predictable pricing scaled by active workflows. Zero execution metering or spike penalties.
            </p>
          </div>

          {/* Pricing Controls: Cycle and Currency */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Monthly vs Annual */}
            <div
              style={{
                display: 'inline-flex',
                backgroundColor: 'var(--surface-1)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                padding: '3px',
              }}
            >
              <button
                onClick={() => setBillingCycle('monthly')}
                style={{
                  border: 'none',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: billingCycle === 'monthly' ? 600 : 400,
                  backgroundColor: billingCycle === 'monthly' ? 'var(--surface-0)' : 'transparent',
                  color: billingCycle === 'monthly' ? 'var(--text-primary)' : 'var(--text-secondary)',
                  boxShadow: billingCycle === 'monthly' ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingCycle('annual')}
                style={{
                  border: 'none',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: billingCycle === 'annual' ? 600 : 400,
                  backgroundColor: billingCycle === 'annual' ? 'var(--surface-0)' : 'transparent',
                  color: billingCycle === 'annual' ? 'var(--text-primary)' : 'var(--text-secondary)',
                  boxShadow: billingCycle === 'annual' ? '0 1px 3px rgba(0,0,0,0.06)' : 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'all 0.15s ease',
                }}
              >
                <span>Annual</span>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 600,
                    backgroundColor: 'var(--status-success-bg, #dcfce7)',
                    color: 'var(--status-success-text, #166534)',
                    padding: '1px 5px',
                    borderRadius: '4px',
                  }}
                >
                  Save 20%
                </span>
              </button>
            </div>

            {/* Currency Switcher */}
            <div
              style={{
                display: 'inline-flex',
                backgroundColor: 'var(--surface-1)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                padding: '3px',
              }}
            >
              <button
                onClick={() => setCurrency('usd')}
                style={{
                  border: 'none',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: currency === 'usd' ? 600 : 400,
                  backgroundColor: currency === 'usd' ? 'var(--surface-0)' : 'transparent',
                  color: currency === 'usd' ? 'var(--text-primary)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                USD ($)
              </button>
              <button
                onClick={() => setCurrency('inr')}
                style={{
                  border: 'none',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: currency === 'inr' ? 600 : 400,
                  backgroundColor: currency === 'inr' ? 'var(--surface-0)' : 'transparent',
                  color: currency === 'inr' ? 'var(--text-primary)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                INR (₹)
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Differentiator Callout Banner */}
      <div
        style={{
          backgroundColor: 'var(--surface-1)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '16px 20px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '20px',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              backgroundColor: 'var(--accent, #3b82f6)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <ShieldCheck size={22} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
                Predictable Budgeting Guarantee
              </span>
              <span
                style={{
                  fontSize: '11px',
                  padding: '2px 7px',
                  borderRadius: '6px',
                  backgroundColor: 'var(--status-success-bg, #dcfce7)',
                  color: 'var(--status-success-text, #166534)',
                  fontWeight: 600,
                }}
              >
                Unlimited Executions
              </span>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '2px 0 0' }}>
              Unlike Zapier's task-metered billing that penalizes scale with overage surprises, SME Connect provides unlimited task executions on all active workflows. You only pay for active workflows.
            </p>
          </div>
        </div>

        {onNavigateWorkflows && (
          <button
            onClick={onNavigateWorkflows}
            className="btn-secondary"
            style={{ fontSize: '13px', padding: '7px 14px', whiteSpace: 'nowrap' }}
          >
            <span>Manage workflows</span>
            <ArrowUpRight size={14} />
          </button>
        )}
      </div>

      {/* Active Workflows Usage Meter Card */}
      <div
        style={{
          backgroundColor: 'var(--surface-0)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '22px 24px',
          marginBottom: '32px',
          boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Workspace Quota & Usage
              </h2>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '6px',
                  backgroundColor:
                    usage.is_limit_reached
                      ? 'var(--status-error-bg, #fee2e2)'
                      : usagePct >= 75
                      ? 'var(--status-warning-bg, #fef3c7)'
                      : 'var(--status-success-bg, #dcfce7)',
                  color:
                    usage.is_limit_reached
                      ? 'var(--status-error-text, #991b1b)'
                      : usagePct >= 75
                      ? 'var(--status-warning-text, #92400e)'
                      : 'var(--status-success-text, #166534)',
                }}
              >
                {usage.is_limit_reached ? 'Quota Reached' : isUnlimited ? 'Unlimited Capacity' : `${usage.remaining_slots} slots remaining`}
              </span>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Current plan: <strong style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{currentPlanTier}</strong> ({subscription?.billing_cycle} billing)
              {subscription?.cancel_at_period_end && ' — Cancels at end of billing cycle'}
            </p>
          </div>

          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {usage.active_workflows}
            </span>
            <span style={{ fontSize: '16px', color: 'var(--text-secondary)' }}>
              {isUnlimited ? ' active (unlimited)' : ` / ${usage.max_active_workflows} active`}
            </span>
          </div>
        </div>

        {/* Progress Bar */}
        {!isUnlimited && (
          <div style={{ marginBottom: '16px' }}>
            <div
              style={{
                width: '100%',
                height: '10px',
                backgroundColor: 'var(--surface-2)',
                borderRadius: '9999px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${usagePct}%`,
                  height: '100%',
                  backgroundColor:
                    usage.is_limit_reached
                      ? 'var(--status-error, #ef4444)'
                      : usagePct >= 75
                      ? 'var(--status-warning, #f59e0b)'
                      : 'var(--status-success, #10b981)',
                  borderRadius: '9999px',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <span>{usagePct}% active quota utilized</span>
              <span>
                {usage.is_limit_reached
                  ? 'Publishing new workflows is paused until upgrade or older flows paused'
                  : `${usage.remaining_slots} more workflow${usage.remaining_slots === 1 ? '' : 's'} can be published`}
              </span>
            </div>
          </div>
        )}

        {/* Sub-breakdown Stats */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '12px',
            paddingTop: '14px',
            borderTop: '1px solid var(--border)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--status-success, #10b981)' }} />
            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Published & Active</div>
              <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>{usage.active_workflows}</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--status-warning, #f59e0b)' }} />
            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Paused (Slots freed)</div>
              <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>{usage.paused_workflows}</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--text-muted, #94a3b8)' }} />
            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Draft Workflows</div>
              <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>{usage.draft_workflows}</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--accent, #3b82f6)' }} />
            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Total Created</div>
              <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>{usage.total_workflows}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Plan Selection Matrix */}
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
          Available Plans
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
          Select the workflow quota that fits your business. Switch or cancel anytime without penalties.
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '20px',
            alignItems: 'stretch',
          }}
        >
          {plans.map((plan) => {
            const isCurrent = currentPlanTier.toLowerCase() === plan.tier.toLowerCase();
            const isPopular = plan.is_popular;

            let priceDisplay = '';
            if (currency === 'inr') {
              if (billingCycle === 'annual') {
                priceDisplay = `₹${Math.round(plan.price_inr_annual / 12).toLocaleString()}`;
              } else {
                priceDisplay = `₹${plan.price_inr_monthly.toLocaleString()}`;
              }
            } else {
              if (billingCycle === 'annual') {
                priceDisplay = `$${Math.round(plan.price_usd_annual / 12)}`;
              } else {
                priceDisplay = `$${plan.price_usd_monthly}`;
              }
            }

            return (
              <div
                key={plan.tier}
                style={{
                  backgroundColor: isCurrent ? 'var(--surface-0)' : 'var(--surface-0)',
                  border: isCurrent
                    ? '2px solid var(--accent, #3b82f6)'
                    : isPopular
                    ? '1.5px solid var(--border-focus, #60a5fa)'
                    : '1px solid var(--border)',
                  borderRadius: '12px',
                  padding: '24px 20px',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  boxShadow: isCurrent ? '0 4px 20px rgba(59, 130, 246, 0.08)' : '0 1px 3px rgba(0,0,0,0.03)',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                }}
              >
                {/* Popular Pill */}
                {isPopular && !isCurrent && (
                  <span
                    style={{
                      position: 'absolute',
                      top: '-10px',
                      right: '18px',
                      backgroundColor: 'var(--accent, #3b82f6)',
                      color: '#ffffff',
                      fontSize: '11px',
                      fontWeight: 600,
                      padding: '2px 10px',
                      borderRadius: '9999px',
                      letterSpacing: '0.02em',
                    }}
                  >
                    Most Popular
                  </span>
                )}

                {/* Current Plan Pill */}
                {isCurrent && (
                  <span
                    style={{
                      position: 'absolute',
                      top: '-10px',
                      right: '18px',
                      backgroundColor: 'var(--status-success, #10b981)',
                      color: '#ffffff',
                      fontSize: '11px',
                      fontWeight: 600,
                      padding: '2px 10px',
                      borderRadius: '9999px',
                      letterSpacing: '0.02em',
                    }}
                  >
                    Current Plan
                  </span>
                )}

                <div style={{ marginBottom: '14px' }}>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    {plan.name}
                  </h3>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0', minHeight: '38px' }}>
                    {plan.description}
                  </p>
                </div>

                {/* Pricing Block */}
                <div style={{ marginBottom: '18px' }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                    <span style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {priceDisplay}
                    </span>
                    <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                      / month
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {plan.price_usd_monthly === 0
                      ? 'Free forever'
                      : billingCycle === 'annual'
                      ? `Billed annually (${currency === 'inr' ? `₹${plan.price_inr_annual.toLocaleString()}` : `$${plan.price_usd_annual}`}/yr)`
                      : 'Billed monthly, cancel anytime'}
                  </div>
                </div>

                {/* Capacity Pill */}
                <div
                  style={{
                    backgroundColor: 'var(--surface-1)',
                    borderRadius: '8px',
                    padding: '8px 12px',
                    marginBottom: '18px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                >
                  <Layers size={16} style={{ color: 'var(--accent, #3b82f6)' }} />
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {plan.max_active_workflows === null
                      ? 'Unlimited Active Workflows'
                      : `${plan.max_active_workflows} Active Workflows`}
                  </span>
                </div>

                {/* Features List */}
                <div style={{ flex: 1, marginBottom: '24px' }}>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '9px' }}>
                    {(plan.features || []).map((feature, idx) => (
                      <li key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '13px', color: 'var(--text-primary)' }}>
                        <Check size={15} style={{ color: 'var(--status-success, #10b981)', marginTop: '2px', flexShrink: 0 }} />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* CTA Button */}
                <button
                  disabled={isCurrent || !isAdmin}
                  onClick={() => handleSelectPlan(plan)}
                  className={isCurrent ? 'btn-secondary' : isPopular ? 'btn-primary' : 'btn-secondary'}
                  style={{
                    width: '100%',
                    justifyContent: 'center',
                    padding: '10px 16px',
                    fontSize: '13px',
                    fontWeight: 500,
                    opacity: isCurrent ? 0.7 : !isAdmin ? 0.6 : 1,
                    cursor: isCurrent || !isAdmin ? 'not-allowed' : 'pointer',
                  }}
                  title={!isAdmin ? 'Admin role required to change subscription' : ''}
                >
                  {isCurrent ? (
                    'Current Plan'
                  ) : !isAdmin ? (
                    'Admin required'
                  ) : (
                    <span>Select {plan.name}</span>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cancellation / Billing Invoices footer */}
      {currentPlanTier !== 'free' && (
        <div
          style={{
            marginTop: '32px',
            padding: '18px 20px',
            borderRadius: '10px',
            border: '1px solid var(--border)',
            backgroundColor: 'var(--surface-1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
              Manage Subscription Lifecycle
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '2px 0 0' }}>
              {subscription?.cancel_at_period_end
                ? 'Your subscription is scheduled to cancel at the end of the current period. Active workflows remain running until then.'
                : 'Need to pause or downgrade? You can schedule cancellation at the end of your billing cycle anytime.'}
            </p>
          </div>

          {isAdmin && !subscription?.cancel_at_period_end && (
            <button
              onClick={handleCancelSubscription}
              disabled={canceling}
              className="btn-danger"
              style={{ fontSize: '12px', padding: '6px 14px' }}
            >
              {canceling ? 'Scheduling...' : 'Cancel subscription'}
            </button>
          )}
        </div>
      )}

      {/* Plan Change Confirmation Modal */}
      {modalPlan && (
        <div className="modal-backdrop" onClick={() => setModalPlan(null)}>
          <div
            className="modal-card"
            style={{ maxWidth: '440px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sparkles size={18} style={{ color: 'var(--accent, #3b82f6)' }} />
                <h3 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>
                  Confirm Plan Switch
                </h3>
              </div>
              <button
                className="btn-icon"
                onClick={() => setModalPlan(null)}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
              >
                ×
              </button>
            </div>

            <div className="modal-body" style={{ padding: '20px 24px' }}>
              <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                You are switching the workspace subscription from <strong style={{ color: 'var(--text-primary)' }}>{currentPlanTier}</strong> to{' '}
                <strong style={{ color: 'var(--text-primary)' }}>{modalPlan.name}</strong> ({billingCycle} billing).
              </p>

              <div
                style={{
                  backgroundColor: 'var(--surface-1)',
                  borderRadius: '8px',
                  padding: '14px 16px',
                  marginBottom: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>New Active Quota:</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {modalPlan.max_active_workflows === null ? 'Unlimited Workflows' : `${modalPlan.max_active_workflows} Active Workflows`}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Execution Metering:</span>
                  <span style={{ fontWeight: 600, color: 'var(--status-success-text, #166534)' }}>
                    Unlimited & Unmetered
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Billing Rate:</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {currency === 'inr'
                      ? `₹${(billingCycle === 'annual' ? modalPlan.price_inr_annual : modalPlan.price_inr_monthly).toLocaleString()}`
                      : `$${billingCycle === 'annual' ? modalPlan.price_usd_annual : modalPlan.price_usd_monthly}`}
                    /{billingCycle === 'annual' ? 'yr' : 'mo'}
                  </span>
                </div>
              </div>

              <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
                Changes take effect immediately. Your quota will expand instantaneously, allowing more workflows to be published.
              </p>
            </div>

            <div className="modal-footer" style={{ padding: '16px 24px', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setModalPlan(null)}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handleConfirmPlanChange}
                disabled={submitting}
              >
                {submitting ? 'Updating...' : `Confirm Switch to ${modalPlan.name}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
