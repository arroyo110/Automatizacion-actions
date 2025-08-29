from rest_framework import serializers
from .models import Insumo
from api.categoriainsumos.serializers import CategoriaInsumoSerializer
class InsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insumo
        fields = ['id', 'nombre', 'cantidad', 'estado', 'categoria_insumo']

    def validate_nombre(self, value):
        # Primero, aplica las validaciones existentes
        if len(value.strip()) < 2:
            raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres")

        # Validación de unicidad (case-insensitive)
        # Buscar insumos con el mismo nombre, ignorando mayúsculas/minúsculas
        qs = Insumo.objects.filter(nombre__iexact=value)

        # Si estamos actualizando un insumo existente, excluimos ese insumo de la búsqueda
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Ya existe un insumo con este nombre.")
        return value

class InsumoDetailSerializer(serializers.ModelSerializer):
    categoria_insumo = CategoriaInsumoSerializer(read_only=True)

    class Meta:
        model = Insumo
        fields = ['id', 'nombre', 'cantidad', 'estado', 'categoria_insumo']
