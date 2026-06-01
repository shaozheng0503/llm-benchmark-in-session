计算 ∫₀¹ x²·eˣ dx。

**采用分部积分法**，设 u = x², dv = eˣdx，则 du = 2x dx, v = eˣ。

第一次分部积分：
∫ x²·eˣ dx = x²·eˣ - ∫ 2x·eˣ dx = x²·eˣ - 2∫ x·eˣ dx

第二次分部积分（对 ∫ x·eˣ dx）：设 u = x, dv = eˣdx, 则 du = dx, v = eˣ。
∫ x·eˣ dx = x·eˣ - ∫ eˣ dx = x·eˣ - eˣ

代回：
∫ x²·eˣ dx = x²·eˣ - 2(x·eˣ - eˣ) + C = x²·eˣ - 2x·eˣ + 2eˣ + C = eˣ(x² - 2x + 2) + C

**代入上下限 [0, 1]：**
- 上限 x=1：e¹·(1 - 2 + 2) = e·1 = e
- 下限 x=0：e⁰·(0 - 0 + 2) = 2

**最终结果：** ∫₀¹ x²·eˣ dx = e - 2
