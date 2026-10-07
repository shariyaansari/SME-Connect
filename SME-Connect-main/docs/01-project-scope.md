| Module                     | First version?   | Why                                                   |
| -------------------------- | ---------------- | ----------------------------------------------------- |
| 1. User & Organization     | P0            | Foundation                                            |
| 2. Connector Management    | P0           | Can't automate without connections                    |
| 3. Workflow Builder        | P0            | Core product                                          |
| 3A. Templates/Onboarding   | P0 | Important differentiator, but don't overbuild         |
| 4. Trigger/Event Detection | P0            | Required for automation                               |
| 5. Execution Engine        | P0            | Core product                                          |
| 6. Error/Logging/Retry     | P0, basic     | Required for trust/debugging                          |
| 7. Monitoring Dashboard    | P0, basic     | User needs to see what happened                       |
| 8. Data Mapping            | P0            | Required for real integrations                        |
| 9. Billing                 | P2         | Doesn't help prove the core product                   |
| 10. Self-hosting           | P2         | Useful differentiator, but not core MVP               |
| 11. WhatsApp               | P1      | Strong differentiator, but not needed to prove engine |
| 12. Export/Import          | P1      | Useful, but not necessary for first working system    |


# SME connect should allow a user to 
```
Create account
      ↓
Create organization
      ↓
Connect external applications
      ↓
Create/select a workflow
      ↓
Configure trigger
      ↓
Configure action
      ↓
Map data
      ↓
Validate workflow
      ↓
Publish workflow
      ↓
Trigger workflow
      ↓
Execute action
      ↓
See result
      ↓
See failure if something goes wrong
```


