from rest_framework import serializers
from .models import Liquidacion
from api.manicuristas.models import Manicurista
from api.manicuristas.serializers import ManicuristaSerializer
from django.db.models import Sum
from datetime import datetime

# CORREGIDO: Importar desde el módulo correcto con manejo de errores
try:
    from api.ventaservicios.models import VentaServicio
except ImportError:
    try:
        from api.ventaservicios.models import VentaServicio
    except ImportError:
        # Si no existe ninguno de los dos, crear una clase dummy
        class VentaServicio:
            objects = None
            
            @classmethod
            def filter(cls, **kwargs):
                return cls.objects.none() if cls.objects else []


class LiquidacionSerializer(serializers.ModelSerializer):
    # Campos calculados de solo lectura (propiedades)
    total_servicios_completados = serializers.ReadOnlyField()
    total_a_pagar = serializers.ReadOnlyField()
    cantidad_servicios_completados = serializers.ReadOnlyField()
    
    # Campos calculados para ventas completadas
    total_ventas_completadas = serializers.SerializerMethodField()
    cantidad_ventas_completadas = serializers.SerializerMethodField()

    class Meta:
        model = Liquidacion
        fields = '__all__'
    
    def get_total_ventas_completadas(self, obj):
        """Calcular total de ventas completadas en el período"""
        try:
            if hasattr(VentaServicio, 'objects') and VentaServicio.objects is not None:
                total = VentaServicio.objects.filter(
                    manicurista=obj.manicurista,
                    fecha_venta__date__range=(obj.fecha_inicio, obj.fecha_final),
                    estado='pagada'
                ).aggregate(total=Sum('total'))['total'] or 0
                return float(total)
            else:
                return 0.0
        except Exception:
            return 0.0
    
    def get_cantidad_ventas_completadas(self, obj):
        """Contar ventas completadas en el período"""
        try:
            if hasattr(VentaServicio, 'objects') and VentaServicio.objects is not None:
                return VentaServicio.objects.filter(
                    manicurista=obj.manicurista,
                    fecha_venta__date__range=(obj.fecha_inicio, obj.fecha_final),
                    estado='pagada'
                ).count()
            else:
                return 0
        except Exception:
            return 0
        
    def validate(self, data):
        # Validar duplicados por manicurista y rango de fechas
        queryset = Liquidacion.objects.filter(
            manicurista=data['manicurista'],
            fecha_inicio=data['fecha_inicio'],
            fecha_final=data['fecha_final']
        )
        
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
            
        if queryset.exists():
            raise serializers.ValidationError("Ya existe una liquidación para esta manicurista en ese rango de fechas.")

        # Validar valores no negativos
        if data['valor'] < 0:
            raise serializers.ValidationError("El valor no puede ser negativo")
        if data['bonificacion'] < 0:
            raise serializers.ValidationError("La bonificación no puede ser negativa")
        
        return data


class LiquidacionDetailSerializer(serializers.ModelSerializer):
    manicurista = ManicuristaSerializer(read_only=True)
    
    # Campos calculados
    total_servicios_completados = serializers.ReadOnlyField()
    total_a_pagar = serializers.ReadOnlyField()
    cantidad_servicios_completados = serializers.ReadOnlyField()
    
    # Campos para ventas
    total_ventas_completadas = serializers.SerializerMethodField()
    cantidad_ventas_completadas = serializers.SerializerMethodField()
    
    class Meta:
        model = Liquidacion
        fields = '__all__'
    
    def get_total_ventas_completadas(self, obj):
        """Calcular total de ventas completadas en el período"""
        try:
            if hasattr(VentaServicio, 'objects') and VentaServicio.objects is not None:
                total = VentaServicio.objects.filter(
                    manicurista=obj.manicurista,
                    fecha_venta__date__range=(obj.fecha_inicio, obj.fecha_final),
                    estado='pagada'
                ).aggregate(total=Sum('total'))['total'] or 0
                return float(total)
            else:
                return 0.0
        except Exception:
            return 0.0
    
    def get_cantidad_ventas_completadas(self, obj):
        """Contar ventas completadas en el período"""
        try:
            if hasattr(VentaServicio, 'objects') and VentaServicio.objects is not None:
                return VentaServicio.objects.filter(
                    manicurista=obj.manicurista,
                    fecha_venta__date__range=(obj.fecha_inicio, obj.fecha_final),
                    estado='pagada'
                ).count()
            else:
                return 0
        except Exception:
            return 0


class LiquidacionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer específico para crear liquidaciones con cálculo automático de valor
    """
    # Campo opcional para auto-calcular valor basado en ventas
    calcular_valor_automatico = serializers.BooleanField(write_only=True, required=False, default=True)
    
    class Meta:
        model = Liquidacion
        fields = ['manicurista', 'fecha_inicio', 'fecha_final', 'valor', 'bonificacion', 'calcular_valor_automatico']
    
    def create(self, validated_data):
        """
        Crear liquidación con cálculo automático de valor si se solicita
        """
        calcular_automatico = validated_data.pop('calcular_valor_automatico', True)
        
        # Si se solicita cálculo automático y no se proporciona valor, calcularlo
        if calcular_automatico and validated_data.get('valor', 0) == 0:
            manicurista = validated_data['manicurista']
            fecha_inicio = validated_data['fecha_inicio']
            fecha_final = validated_data['fecha_final']
            
            # Calcular total de ventas completadas
            try:
                if hasattr(VentaServicio, 'objects') and VentaServicio.objects is not None:
                    total_ventas = VentaServicio.objects.filter(
                        manicurista=manicurista,
                        fecha_venta__date__range=(fecha_inicio, fecha_final),
                        estado='pagada'
                    ).aggregate(total=Sum('total'))['total'] or 0
                else:
                    total_ventas = 0
            except Exception:
                total_ventas = 0
            
            validated_data['valor'] = total_ventas
        
        return Liquidacion.objects.create(**validated_data)


class LiquidacionUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar liquidaciones con opción de recalcular
    """
    recalcular_citas_completadas = serializers.BooleanField(write_only=True, required=False, default=False)
    recalcular_valor_ventas = serializers.BooleanField(write_only=True, required=False, default=False)
    
    class Meta:
        model = Liquidacion
        fields = ['valor', 'bonificacion', 'recalcular_citas_completadas', 'recalcular_valor_ventas']
    
    def update(self, instance, validated_data):
        recalcular_citas = validated_data.pop('recalcular_citas_completadas', False)
        recalcular_ventas = validated_data.pop('recalcular_valor_ventas', False)
        
        # Actualizar campos normales
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Recalcular citas completadas si se solicita
        if recalcular_citas:
            instance.calcular_citas_completadas()
        
        # Recalcular valor basado en ventas si se solicita
        if recalcular_ventas:
            try:
                if hasattr(VentaServicio, 'objects') and VentaServicio.objects is not None:
                    total_ventas = VentaServicio.objects.filter(
                        manicurista=instance.manicurista,
                        fecha_venta__date__range=(instance.fecha_inicio, instance.fecha_final),
                        estado='pagada'
                    ).aggregate(total=Sum('total'))['total'] or 0
                    
                    instance.valor = total_ventas
                else:
                    # Si no existe el modelo de ventas, mantener el valor actual
                    pass
            except Exception:
                # En caso de error, mantener el valor actual
                pass
        
        instance.save()
        return instance
