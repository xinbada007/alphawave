from typing import Callable, List, Optional, Tuple, Dict, Any
from functools import wraps
from alphaflow.core.schema.models import ResearchPack
from alphaflow.core.facade import ResearchPackFacade


class MetricEngine:
    """
    声明式基本面计算引擎 (V4 语义域分桶)
    
    升级要点：
    1. 装饰器增加 domain 参数，指标按语义域分桶
    2. 输出嵌套 dict，域名即文档
    3. 幂等防护：同名指标不重复注册
    """
    _registry: List[Dict[str, Any]] = []

    @classmethod
    def fundamental_metric(
        cls,
        feature_name: str,
        domain: str,
        depends_on: List[Tuple[str, str, str]],
        optional_depends_on: Optional[List[Tuple[str, str, str]]] = None,
    ):
        """
        高阶装饰器 (V4.1)
        
        Args:
            feature_name: 指标短名，域内唯一 (如 "ROE")
            domain: 语义域标签 (如 "profitability_ttm")
            depends_on: 强制依赖三元组列表（缺失任一则跳过计算）
            optional_depends_on: 弱依赖三元组列表（缺失时传 None，不阻断计算）
                                 注意：函数签名的参数顺序必须严格匹配
                                 depends_on 在前，optional_depends_on 在后
        """
        def decorator(func: Callable):
            # 🚀 幂等防护：同名指标不重复注册
            if any(m["feature_name"] == feature_name for m in cls._registry):
                return func
            cls._registry.append({
                "feature_name": feature_name,
                "domain": domain,
                "depends_on": depends_on,
                "optional_depends_on": optional_depends_on or [],
                "func": func
            })
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    @classmethod
    def execute_all(cls, facade: ResearchPackFacade, pack: ResearchPack):
        """沙箱执行所有注册指标，按域分桶输出"""
        bucketed: Dict[str, Dict[str, float]] = {}
        consumed_keys: set[str] = set()
        
        for meta in cls._registry:
            dep_domain = ""
            dep_key = ""
            try:
                args: List[Any] = []
                missing_data = False
                
                # 强依赖：缺失任一即跳过
                for period_type, dep_domain, dep_key in meta["depends_on"]:
                    val = facade.resolve_dependency(period_type, dep_domain, dep_key)
                    if val is None:
                        missing_data = True
                        break
                    args.append(val)
                
                if missing_data:
                    print(f"  [MetricEngine] ⚠️ Skipped '{meta['feature_name']}': Missing dependency [{dep_domain}] -> {dep_key}")
                    continue
                
                # 弱依赖：缺失时传 None，不阻断计算
                for period_type, dep_domain, dep_key in meta.get("optional_depends_on", []):
                    val = facade.resolve_dependency(period_type, dep_domain, dep_key)
                    args.append(val)  # None is OK
                
                result = meta["func"](*args)
                
                if result is not None:
                    bucket_name = meta["domain"]
                    if bucket_name not in bucketed:
                        bucketed[bucket_name] = {}
                    bucketed[bucket_name][meta["feature_name"]] = result
                    
                    for _, _, sk in meta["depends_on"]:
                        consumed_keys.add(sk)
                    for _, _, sk in meta.get("optional_depends_on", []):
                        consumed_keys.add(sk)
                        
            except Exception as e:
                print(f"  [MetricEngine] ⚠️ Error calculating {meta['feature_name']}: {e}")
        
        # 显式赋值触发 Pydantic V2 追踪
        if bucketed:
            pack.distilled_features.fundamental_metrics = bucketed
        for key in consumed_keys:
            pack.registry.claim_standard_key(key)
