
    @classmethod
    def upsert_1(cls, new_record: _TSecurity, only_check=False) -> tuple[str ,Optional[_TSecurity]]:
        """插入或更新数据
        规则：
        1. 查找 code 对应的最新记录
        2. 如果最新记录的数据与待插入数据一致（调用 old_record.__eq__(new_record)），则只更新 updated_at
        3. 否则插入新记录
        Returns:
            成功 insert 返回旧记录
        """
        result = (None, None)
        session = cls.get_session()
        if new_record.updated_at is None:
            new_record.updated_at = datetime.now()

        try:
            # 查找 InstrumentID, ExchangeID 的最新记录
            code = SecurityCode((new_record.InstrumentID, new_record.ExchangeID))
            latest_record = cls._get_latest_by_code(session, code, new_record.updated_at) # type: _TSecurity

            if latest_record:
                if latest_record.updated_at >= new_record.updated_at:
                    T("数据库的更新鲜，无需操作", _level='PASS',
                    stock=code.full_code, new=new_record.updated_at, updated_at=latest_record.updated_at) if cls._is_debug else None
                    return (None, latest_record)

                # 检查记录是否相同(已排除 id, created_at, updated_at 等字段)
                if latest_record == new_record:
                    # UPDATE when data is same.
                    I("更新 updated_at", _level='UPDATE', latest_record=latest_record) if cls._is_debug else None
                    if not only_check:
                        latest_record.update(updated_at = new_record.updated_at)
                        session.commit()
                    return ('update', latest_record)
                else:
                    I("数据有变化，插入新记录", _level='INSERT', latest_record=latest_record) if cls._is_debug else None
                    result = ('insert', latest_record)
            else:
                I("首次插入记录", _level='NEW', new_record=new_record) if cls._is_debug else None
                result = ('new', new_record)
                
            # INSERT
            if not only_check:
                session.add(new_record)
                session.commit()
                session.refresh(new_record)

            I(f"插入新记录", _level='INSERT',
              旧id=latest_record.id if latest_record else None, 新id=new_record.id) if cls._is_debug else None
            return result

        except Exception as e:
            session.rollback()

            import traceback
            traceback.print_exc()
            raise Exception(f"操作数据库时出错: {e}")
        finally:
            cls.close_session()