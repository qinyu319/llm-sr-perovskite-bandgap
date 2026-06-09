# Final M4 Decision

Final frozen M4 formula

Formula:
Eg = 1.55527 - 1.10253*Sn + 0.34320*Br + 1.61932*Cl + 0.12268*Cs + 0.91702*Sn² + 0.36607*Br² - 0.22716*Cs·Sn - 0.32528*Cs·Cl

Terms: Sn, Br, Cl, Cs, Sn², Br², Cs·Sn, Cs·Cl

Primary evidence:
- Fixed 5-fold CV RMSE: 0.057532 eV; M4-full reference: 0.058333 eV.
- Repeated 5-fold CV RMSE: 0.058056 eV; M4-full reference: 0.060061 eV.
- k: 8 vs full 14.
- Max VIF: 15.79 vs full 3250.06.
- Bootstrap sign stability mean/min: 1.000/0.999; full 0.946/0.707.
- Cl-rich RMSE: 0.111797 vs full 0.108541.
- MA-rich RMSE: 0.060097 vs full 0.057961.

Decision:
Freeze this 8-term M4. It keeps the minimum Cs interaction encoding supported by CV and removes high-collinearity or unstable terms: Cl2, BrCl, SnCl, Cs2, CsBr, and MA.
